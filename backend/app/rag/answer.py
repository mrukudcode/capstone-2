"""
Answer generation layer.

IMPORTANT:
- The LLM NEVER makes PASS/FAIL decisions.
- The deterministic rule engine handles claim validation.
- The LLM is used only for policy-document explanations / RAG QA.
- The LLM receives only the user's question and retrieved policy chunks.
- If Groq is unavailable, the system falls back to extractive answers.
"""

import os
from abc import ABC, abstractmethod
from typing import List

from app.rag.retrieve import RetrievedChunk


# --------------------------------------------------
# SYSTEM PROMPT
# --------------------------------------------------

SYSTEM_PROMPT = (
    "You are a policy-document explanation assistant.\n"
    "Answer ONLY from the supplied source passages.\n"
    "Do not use outside knowledge.\n"
    "Do not infer missing policy terms.\n"
    "Do not invent coverage, exclusions, limits, waiting periods, "
    "deductions, or eligibility conditions.\n"
    "If the answer is not supported by the supplied passages, say:\n"
    "'Not found in the selected policy source.'\n"
    "Cite every factual claim using the supplied document ID and page number.\n"
)


# --------------------------------------------------
# PROVIDER INTERFACE
# --------------------------------------------------

class LLMProvider(ABC):

    @abstractmethod
    def generate_answer(
        self,
        question: str,
        chunks: List[RetrievedChunk],
    ) -> str:
        ...


# --------------------------------------------------
# EXTRACTIVE FALLBACK
# --------------------------------------------------

class ExtractiveProvider(LLMProvider):
    """
    No LLM call.

    Returns the retrieved policy passages directly.
    This is the fallback if Groq is unavailable.
    """

    def generate_answer(
        self,
        question: str,
        chunks: List[RetrievedChunk],
    ) -> str:

        if not chunks:
            return "Not found in the selected policy source."

        parts = [
            f"Based on {c.document_id} (page {c.page}): {c.text}"
            for c in chunks
        ]

        return "\n\n".join(parts)


# --------------------------------------------------
# GROQ PROVIDER
# --------------------------------------------------

class GroqProvider(LLMProvider):
    """
    Uses Groq through the OpenAI-compatible Python client.

    Groq API endpoint:
        https://api.groq.com/openai/v1
    """

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-120b",
    ):
        self.api_key = api_key
        self.model = model

    def generate_answer(
        self,
        question: str,
        chunks: List[RetrievedChunk],
    ) -> str:

        if not chunks:
            return "Not found in the selected policy source."

        try:
            from openai import OpenAI

            # ------------------------------------------
            # Prepare ONLY retrieved policy passages
            # ------------------------------------------

            passages = "\n\n".join(
                f"[{c.document_id}, page {c.page}]: {c.text}"
                for c in chunks
            )

            # ------------------------------------------
            # Groq client
            # ------------------------------------------

            client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1",
            )

            # ------------------------------------------
            # Actual LLM call
            # ------------------------------------------

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Question: {question}\n\n"
                            f"Source passages:\n{passages}"
                        ),
                    },
                ],
                temperature=0,
            )

            answer = response.choices[0].message.content

            if not answer:
                raise RuntimeError(
                    "Groq returned an empty response."
                )

            print(
                f"[RAG] Groq LLM used successfully "
                f"(model={self.model})"
            )

            return answer

        except Exception as e:

            # IMPORTANT:
            # Do NOT silently hide API errors.
            print(
                f"[RAG] Groq API error: "
                f"{type(e).__name__}: {e}"
            )

            print(
                "[RAG] Falling back to ExtractiveProvider."
            )

            return ExtractiveProvider().generate_answer(
                question,
                chunks,
            )


# --------------------------------------------------
# PROVIDER SELECTION
# --------------------------------------------------

def get_provider() -> LLMProvider:
    """
    Select Groq if GROQ_API_KEY exists.

    Otherwise use the safe extractive fallback.

    The API key is NEVER hardcoded.
    """

    groq_key = os.environ.get("GROQ_API_KEY")

    if groq_key:
        print("[RAG] Using GroqProvider")
        return GroqProvider(groq_key)

    print(
        "[RAG] GROQ_API_KEY not found. "
        "Using ExtractiveProvider."
    )

    return ExtractiveProvider()
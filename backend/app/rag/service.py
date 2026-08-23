"""
Orchestrates: retrieve -> threshold check -> answer generation -> citations.
This is the ONLY entry point the API layer should call.
"""
from app.rag.retrieve import retrieve
from app.rag.answer import get_provider


def answer_question(question: str, policy_version_id: str, top_k: int = 3) -> dict:
    chunks = retrieve(question, policy_version_id, top_k=top_k)

    if not chunks:
        return {
            "found": False,
            "answer": "Not found in the selected policy source.",
            "citations": [],
            "sources": [],
        }

    provider = get_provider()
    answer_text = provider.generate_answer(question, chunks)

    citations = [
        {
            "document": c.document_id,
            "page": c.page,
            "chunk_id": c.chunk_id,
            "relevance_score": round(c.similarity_score, 4),
        }
        for c in chunks
    ]
    sources = [
        {"document": c.document_id, "page": c.page, "text": c.text}
        for c in chunks
    ]

    return {
        "found": True,
        "answer": answer_text,
        "citations": citations,
        "sources": sources,
    }

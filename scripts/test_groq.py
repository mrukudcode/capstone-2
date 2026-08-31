from app.services.llm_service import call_llm


result = call_llm(
    """
    You are a test assistant.
    Return JSON only.
    """,
    """
    Return:
    {
        "status": "working"
    }
    """
)

print(result)
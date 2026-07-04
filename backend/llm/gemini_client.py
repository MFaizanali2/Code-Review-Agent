from backend.llm.llm_client import LLMClient, create_gemini_client


class GeminiClient(LLMClient):
    """Gemini provider — created via factory for consistent config."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        client = create_gemini_client(api_key=api_key, model=model)
        self.__dict__.update(client.__dict__)

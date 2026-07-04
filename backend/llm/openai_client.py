from backend.llm.llm_client import LLMClient, create_openai_client


class OpenAIClient(LLMClient):
    """OpenAI provider — created via factory for consistent config."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        client = create_openai_client(api_key=api_key, model=model)
        self.__dict__.update(client.__dict__)

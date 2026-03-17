"""Embedding provider abstraction."""

from config.settings import get_settings


def get_embedding_function():
    """Return the appropriate embedding function based on configuration."""
    settings = get_settings()

    if settings.active_provider == "azure":
        from langchain_openai import AzureOpenAIEmbeddings
        return AzureOpenAIEmbeddings(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_key,
            api_version=settings.azure_openai_api_version,
            azure_deployment=settings.azure_openai_embedding_deployment,
        )
    elif settings.active_provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        kwargs = {
            "api_key": settings.openai_api_key,
            "model": "text-embedding-3-small",
        }
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return OpenAIEmbeddings(**kwargs)
    else:
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

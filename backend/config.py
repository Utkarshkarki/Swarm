import os
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)


class Settings:
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.2")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "ollama")
    DB_PATH: str = os.getenv("DB_PATH", "swarm.db")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", "90"))

    # Langfuse Observability
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # Pricing per 1M tokens ($)
    INPUT_TOKEN_PRICE_PER_1M: float = float(os.getenv("INPUT_TOKEN_PRICE_PER_1M", "0.15"))
    OUTPUT_TOKEN_PRICE_PER_1M: float = float(os.getenv("OUTPUT_TOKEN_PRICE_PER_1M", "0.60"))


settings = Settings()


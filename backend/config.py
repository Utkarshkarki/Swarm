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


settings = Settings()

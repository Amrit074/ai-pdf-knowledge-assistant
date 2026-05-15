from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PDF Knowledge Assistant"
    app_env: str = "development"
    log_level: str = "INFO"

    upload_dir: Path = Path("storage/uploads")
    index_dir: Path = Path("storage/index")

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = Field(default=900, ge=200)
    chunk_overlap: int = Field(default=150, ge=0)
    top_k: int = Field(default=5, ge=1, le=20)

    llm_provider: str = "mock"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def resolve_path(self, value: Path) -> Path:
        if value.is_absolute():
            return value
        return self.project_root / value


@lru_cache
def get_settings() -> Settings:
    return Settings()

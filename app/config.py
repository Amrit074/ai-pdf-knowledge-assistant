from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PDF Knowledge Assistant"
    app_env: str = "development"
    log_level: str = "INFO"

    upload_dir: Path = Path("storage/uploads")
    index_dir: Path = Path("storage/index")
    database_url: str = "sqlite:///storage/app.db"
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, ge=5, le=1440)
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    oauth_state_secret: str = "change-this-oauth-state-secret"
    frontend_url: str = "http://localhost:8000/"
    cors_origins: str = "http://localhost:8000"

    embedding_provider: str = "hash"
    embedding_model: str = "models/gemini-embedding-001"
    embedding_dimension: int = Field(default=768, ge=64)
    embedding_batch_size: int = Field(default=16, ge=1, le=100)
    chunk_size: int = Field(default=900, ge=200)
    chunk_overlap: int = Field(default=150, ge=0)
    top_k: int = Field(default=5, ge=1, le=20)
    min_retrieval_score: float = Field(default=0.20, ge=-1, le=1)
    max_upload_mb: int = Field(default=10, ge=1, le=50)

    llm_provider: str = "mock"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.app_env.lower() == "production":
            for name in ("jwt_secret_key", "oauth_state_secret"):
                value = getattr(self, name)
                if len(value) < 32 or value.startswith("change-this"):
                    raise ValueError(f"{name} must be a strong secret of at least 32 characters in production")
            if self.jwt_secret_key == self.oauth_state_secret:
                raise ValueError("JWT and OAuth state secrets must differ")
        return self

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def resolve_path(self, value: Path) -> Path:
        if value.is_absolute():
            return value
        return self.project_root / value

    def resolve_database_url(self) -> str:
        if self.database_url.startswith("sqlite:///") and not self.database_url.startswith("sqlite:////"):
            return "sqlite:///" + str(self.resolve_path(Path(self.database_url.removeprefix("sqlite:///"))))
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()

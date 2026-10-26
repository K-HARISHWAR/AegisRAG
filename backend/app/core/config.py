"""Centralized application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable loading and validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core Application
    PROJECT_NAME: str = "AegisRAG Enterprise Assistant"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Server Configuration
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Security & Authentication
    SECRET_KEY: str = Field(
        default="dev-secret-key-minimum-32-characters-for-local-testing-only!",
        description="Cryptographic secret key for signing tokens",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database (Defaults to local SQLite for zero-config dev; override with PostgreSQL in production)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "aegisrag"
    DATABASE_URL: str = "sqlite+aiosqlite:///backend/data/aegisrag.db"

    # Storage Configuration
    STORAGE_TYPE: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_DIR: str = "backend/data/uploads"
    MAX_FILE_SIZE_MB: int = 20
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "docx", "xlsx"]

    # Vector Database
    VECTOR_STORE_TYPE: Literal["chroma"] = "chroma"
    CHROMA_PERSIST_DIRECTORY: str = "backend/data/chroma"
    CHROMA_COLLECTION_NAME: str = "aegis_rag_chunks"

    # Embeddings
    EMBEDDING_PROVIDER: str = "huggingface"
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384

    # LLM Provider
    LLM_PROVIDER: Literal["groq", "openai"] = "groq"
    GROQ_API_KEY: str | None = None
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 1024
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str = "https://api.openai.com/v1"

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}, got '{v}'")
        return upper_v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Fail fast if production settings use insecure defaults."""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production environment")
            if (
                len(self.SECRET_KEY) < 32
                or "dev" in self.SECRET_KEY.lower()
                or "secret" in self.SECRET_KEY.lower()
            ):
                raise ValueError(
                    "SECRET_KEY must be a secure random string of at least 32 characters in production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()

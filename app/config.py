"""Load and validate server configuration from the environment and local .env file."""

from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralize provider credentials, retrieval limits, and persistent data paths.

    Environment variables override .env values. SecretStr prevents accidental key
    disclosure in representations; ``configured`` checks presence, not validity.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    euri_api_key: SecretStr = SecretStr("")
    euri_base_url: str = "https://api.euron.one/api/v1/euri"
    euri_model: str = "gemini-3.5-flash-lite"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    data_dir: Path = Path("data")
    chunk_size: int = Field(900, ge=200, le=1400)
    chunk_overlap: int = Field(150, ge=0)
    min_similarity: float = Field(0.35, ge=-1, le=1)
    llm_timeout: float = Field(60, ge=1, le=180)
    max_upload_mb: int = Field(10, ge=1, le=50)

    @model_validator(mode="after")
    def valid_overlap(self):
        """Reject an overlap that would prevent chunk windows from advancing."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self

    @property
    def configured(self):
        """Return whether a nonblank EURI key exists, without exposing its value."""
        return bool(self.euri_api_key.get_secret_value().strip())

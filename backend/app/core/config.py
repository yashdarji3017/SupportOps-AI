from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = Field(
        default="Customer Support Triage Bot",
        description="Application name.",
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Application version.",
    )
    DEBUG: bool = Field(
        default=False,
        description="Debug mode toggle.",
    )
    MAX_CONCURRENT_REQUESTS: int = Field(
        default=5,
        ge=1,
        description="Maximum concurrent ticket processing operations per process.",
    )
    CONFIDENCE_THRESHOLD: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score threshold required to avoid human escalation.",
    )
    LLM_PROVIDER: Literal["mock", "gemini"] = Field(
        default="mock",
        description="Active LLM provider (mock or gemini).",
    )
    GEMINI_API_KEY: str | None = Field(
        default=None,
        description="Google Gemini API key required when LLM_PROVIDER is 'gemini'.",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-flash",
        description="Google Gemini model identifier.",
    )
    LLM_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        ge=1.0,
        description="Timeout for LLM API calls in seconds.",
    )
    LLM_MAX_RETRIES: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Max retries for transient LLM provider failures.",
    )
    REQUEST_TIMEOUT_SECONDS: float = Field(
        default=60.0,
        ge=5.0,
        description="Total per-ticket processing timeout in seconds.",
    )

    @property
    def gemini_model(self) -> str:
        """Return the configured Gemini model identifier."""
        return self.GEMINI_MODEL

    @property
    def google_api_key(self) -> str | None:
        """Return the configured Google Gemini API key."""
        return self.GEMINI_API_KEY

    @field_validator("CONFIDENCE_THRESHOLD")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate that confidence threshold is within valid probability bounds [0.0, 1.0].

        Args:
            v: The configured confidence threshold.

        Returns:
            The validated float value.

        Raises:
            ValueError: If value is not between 0.0 and 1.0 inclusive.
        """
        if not (0.0 <= v <= 1.0):
            raise ValueError("CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        return v

    @field_validator("MAX_CONCURRENT_REQUESTS")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        """Validate that concurrency capacity is at least 1.

        Args:
            v: The configured maximum concurrent requests integer.

        Returns:
            The validated integer value.

        Raises:
            ValueError: If value is less than 1.
        """
        if v < 1:
            raise ValueError("MAX_CONCURRENT_REQUESTS must be at least 1")
        return v

    @model_validator(mode="after")
    def validate_provider_keys(self) -> "Settings":
        """Verify required API credentials when external providers are selected.

        Returns:
            The validated Settings instance.

        Raises:
            ValueError: If gemini provider is active without an API key.
        """
        if self.LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY must be configured when LLM_PROVIDER is set to 'gemini'."
            )
        return self


settings: Settings = Settings()


def get_settings() -> Settings:
    """Retrieve application settings singleton instance.

    Returns:
        The global Settings instance.
    """
    return settings


def get_google_api_key() -> str | None:
    """Retrieve configured Google API key from application settings.

    Returns:
        The API key string if configured, or None.
    """
    return settings.GEMINI_API_KEY


def get_gemini_model_name() -> str:
    """Retrieve configured Gemini model identifier from application settings.

    Returns:
        The Gemini model identifier string.
    """
    return settings.GEMINI_MODEL

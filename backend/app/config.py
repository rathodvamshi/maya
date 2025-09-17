# backend/app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Central configuration for the application.
    Reads environment variables from a `.env` file by default.
    """

    # ==================================================
    # 🔹 Database & Security
    # ==================================================
    DATABASE_URL: str                    # SQLAlchemy database URL
    SECRET_KEY: str                      # JWT signing key
    ALGORITHM: str                       # JWT algorithm (e.g., HS256)
    ACCESS_TOKEN_EXPIRE_MINUTES: int     # Expiry for access tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int       # Expiry for refresh tokens

    # ==================================================
    # 🔹 AI / Embeddings / Vector DB
    # ==================================================
    PINECONE_API_KEY: str                # Pinecone API key
    PINECONE_ENVIRONMENT: str            # Pinecone region (e.g., "us-east-1")

    # AI provider API keys (all REQUIRED now)
    GEMINI_API_KEYS: str                 # Google Gemini
    COHERE_API_KEY: str                  # Cohere
    ANTHROPIC_API_KEY: str               # Anthropic Claude

    # If one provider fails, wait N seconds before retry
    AI_PROVIDER_FAILURE_TIMEOUT: int = 300  

    # ==================================================
    # 🔹 Redis (optional, for caching / sessions)
    # ==================================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # ==================================================
    # 🔹 Email Configuration
    # ==================================================
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    # ==================================================
    # 🔹 Rate Limits / Quotas
    # ==================================================
    API_MONTHLY_LIMIT: int = 20  # Max requests per month per user

    # ==================================================
    # 🔹 Config Behavior
    # ==================================================
    model_config = SettingsConfigDict(
        env_file=".env",      # Load vars from .env
        extra="forbid"        # Forbid undefined env vars (safety)
    )


# Create a global settings instance
settings = Settings()

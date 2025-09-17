# backend/app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application configuration.
    All values are read from environment variables or a `.env` file.
    """

    # ==================================================
    # 🔹 Database & Security
    # ==================================================
    DATABASE_URL: str                    # SQLAlchemy database URL
    SECRET_KEY: str                      # JWT signing key
    ALGORITHM: str                       # JWT algorithm (e.g., HS256)
    ACCESS_TOKEN_EXPIRE_MINUTES: int     # Expiry for access tokens (minutes)
    REFRESH_TOKEN_EXPIRE_DAYS: int       # Expiry for refresh tokens (days)

    # ==================================================
    # 🔹 AI / Embeddings / Vector DB
    # ==================================================
    PINECONE_API_KEY: str                # Pinecone API key
    PINECONE_ENVIRONMENT: str            # Pinecone region (e.g., "us-east-1")

    # AI provider API keys (all REQUIRED for now)
    GEMINI_API_KEYS: str                 # Google Gemini (comma-separated keys)
    COHERE_API_KEY: str                  # Cohere API key
    ANTHROPIC_API_KEY: str               # Anthropic Claude API key

    # If one provider fails, wait N seconds before retrying
    AI_PROVIDER_FAILURE_TIMEOUT: int = 300  

    # ==================================================
    # 🔹 Redis (optional, for caching / sessions)
    # ==================================================
    REDIS_HOST: str = "localhost"        # Redis host (default: local)
    REDIS_PORT: int = 6379               # Redis port
    REDIS_DB: int = 0                    # Redis DB index
    REDIS_PASSWORD: str | None = None    # Redis password (if set)

    # ==================================================
    # 🔹 Neo4j Knowledge Graph
    # ==================================================
    NEO4J_URI: str                       # Example: "bolt://localhost:7687"
    NEO4J_USER: str                      # Neo4j username
    NEO4J_PASSWORD: str                  # Neo4j password

    # ==================================================
    # 🔹 Email Configuration
    # ==================================================
    MAIL_USERNAME: str                   # SMTP username
    MAIL_PASSWORD: str                   # SMTP password / App password
    MAIL_FROM: str                       # Default sender email
    MAIL_SERVER: str = "smtp.gmail.com"  # SMTP server
    MAIL_PORT: int = 587                 # Port (587 = TLS, 465 = SSL)
    MAIL_STARTTLS: bool = True           # Enable STARTTLS
    MAIL_SSL_TLS: bool = False           # Enable SSL/TLS (usually for port 465)

    # ==================================================
    # 🔹 Rate Limits / Quotas
    # ==================================================
    API_MONTHLY_LIMIT: int = 20          # Max requests per month per user

    # ==================================================
    # 🔹 Config Behavior
    # ==================================================
    model_config = SettingsConfigDict(
        env_file=".env",                 # Load variables from .env file
        extra="forbid"                   # Forbid undefined env vars (safety)
    )


# ✅ Create a global settings instance
settings = Settings()

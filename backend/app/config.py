# backend/app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT & Security
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # AI API Keys
    GEMINI_API_KEYS: str
    COHERE_API_KEY: str
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str | None = None  # optional if not always used

    # Email settings
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool

    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # API usage limits
    API_MONTHLY_LIMIT: int = 20

    # Optional MongoDB (if you use it separately from DATABASE_URL)
    MONGO_URL: str | None = None
    MONGO_DB: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

settings = Settings()

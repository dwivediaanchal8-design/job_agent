"""
config.py — Application Configuration
=====================================
All settings are loaded from the .env file.
Never hardcode secrets. Use this config throughout the app.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """
    Central configuration class.
    All values come from environment variables / .env file.
    """

    # --- App ---
    app_name: str = Field(default="Job Search AI Agent", env="APP_NAME")
    app_env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=True, env="DEBUG")
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    log_file: str = Field(default="logs/agent.log", env="LOG_FILE")

    # --- Database ---
    database_url: str = Field(..., env="DATABASE_URL")
    database_url_sync: str = Field(..., env="DATABASE_URL_SYNC")

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # --- Security ---
    master_encryption_key: str = Field(..., env="MASTER_ENCRYPTION_KEY")
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=1440, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # --- OpenAI / OpenRouter ---
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", env="OPENAI_BASE_URL"
    )
    openai_model: str = Field(default="openai/gpt-4o", env="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        default="openai/text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL"
    )

    # --- Phase 3: AI Features ---
    cover_letter_enabled: bool = Field(default=True, env="COVER_LETTER_ENABLED")

    # --- CAPTCHA ---
    twocaptcha_api_key: str = Field(default="", env="TWOCAPTCHA_API_KEY")

    # --- File Storage ---
    upload_dir: str = Field(default="./uploads", env="UPLOAD_DIR")
    max_file_size_mb: int = Field(default=10, env="MAX_FILE_SIZE_MB")

    # --- Rate Limiting ---
    max_applications_per_day: int = Field(
        default=50, env="MAX_APPLICATIONS_PER_DAY"
    )
    job_match_threshold: int = Field(default=70, env="JOB_MATCH_THRESHOLD")

    # --- Error Alerting ---
    smtp_host: str = Field(default="", env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_user: str = Field(default="", env="SMTP_USER")
    smtp_pass: str = Field(default="", env="SMTP_PASS")
    admin_email: str = Field(default="", env="ADMIN_EMAIL")
    slack_webhook_url: str = Field(default="", env="SLACK_WEBHOOK_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    Use as FastAPI dependency: settings = Depends(get_settings)
    """
    return Settings()


# Global settings instance for direct imports
settings = get_settings()

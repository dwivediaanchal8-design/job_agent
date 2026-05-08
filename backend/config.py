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

    # --- OpenAI ---
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", env="OPENAI_MODEL")

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

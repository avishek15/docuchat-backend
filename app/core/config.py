"""Configuration management for the application."""

# import os
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # App settings
    app_name: str = Field(default="DocuChat API", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")

    # AWS Lambda settings
    aws_region: str = Field(default="ap-southeast-1", env="AWS_REGION")

    # Google Sheets settings
    google_project_id: Optional[str] = Field(default=None, env="GOOGLE_PROJECT_ID")
    google_private_key_id: Optional[str] = Field(
        default=None, env="GOOGLE_PRIVATE_KEY_ID"
    )
    google_private_key: Optional[str] = Field(default=None, env="GOOGLE_PRIVATE_KEY")
    google_client_email: Optional[str] = Field(default=None, env="GOOGLE_CLIENT_EMAIL")
    google_sheets_id: Optional[str] = Field(default=None, env="GOOGLE_SHEETS_ID")
    google_worksheet_name: str = Field(default="Leads", env="GOOGLE_WORKSHEET_NAME")

    # Turso Database settings
    turso_database_url: Optional[str] = Field(default=None, env="TURSO_DATABASE_URL")
    turso_auth_token: Optional[str] = Field(default=None, env="TURSO_AUTH_TOKEN")
    local_db_path: str = Field(default="local.db", env="LOCAL_DB_PATH")

    # External API settings
    api_timeout: int = Field(default=30, env="API_TIMEOUT")
    max_retries: int = Field(default=3, env="MAX_RETRIES")

    # Pinecone settings
    pinecone_api_key: Optional[str] = Field(default=None, env="PINECONE_API_KEY")
    pinecone_index_name: str = Field(
        default="ta-sample-docs", env="PINECONE_INDEX_NAME"
    )
    pinecone_max_concurrent: int = Field(default=15, env="PINECONE_MAX_CONCURRENT")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()

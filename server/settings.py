"""Environment-backed settings for the local web pilot."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Domestic Job Search"
    app_version: str = "0.1.0"
    database_url: str = "sqlite:///./runtime/web.db"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "job-hunter"
    default_model_key: str = ""
    model_credential_key: str = ""
    llm_endpoint: str = "https://api.openai.com/v1/chat/completions"
    llm_model: str = "gpt-4o-mini"
    chromium_profile_root: str = "runtime/chromium"
    initial_admin_username: str = ""
    initial_admin_password: str = ""

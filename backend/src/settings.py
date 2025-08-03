from tuneapi import tt, ta
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from supabase import Client


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_prefix="ASAM_",
        env_file_encoding="utf-8",
    )

    # database settings
    db_url: str

    # server settings
    host: str = "0.0.0.0"
    port: int = 8000
    prod: bool = False

    # auth settings
    jwt_secret: str
    jwt_algorithm: str = "HS256"

    # admin settings
    admin_default_password_length: int = 12
    max_upload_file_size: int = 25  # MB
    allowed_upload_extensions: str = "pdf/txt/docx"
    generated_content_retention_days: int = 30

    # model settings
    openai_token: str

    # supabase settings
    supabase_url: str
    supabase_key: str

    # mode
    echo_db: bool = False

    def is_valid_upload_extension(self, extension: str) -> bool:
        return extension.lower() in self.allowed_upload_extensions.split("/")


settings = Settings()


def get_llm(id: str):
    return ta.Openai(id=id, api_token=settings.openai_token)


def get_supabase_client() -> Client:
    return Client(settings.supabase_url, settings.supabase_key)

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    telegram_token: str
    postgres_url: str
    
    # API Keys
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None
    
    # URLs
    webhook_url: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    
    # Model names
    router_model: str = "qwen/qwen3-next-80b-a3b-instruct:free"
    extractor_model: str = "qwen/qwen3-next-80b-a3b-instruct:free"
    analyst_model: str = "qwen/qwen3-next-80b-a3b-instruct:free"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

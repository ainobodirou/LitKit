from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from pathlib import Path
from functools import lru_cache

class Settings(BaseSettings):
    litellm_base_url: str = "http://localhost:4000/v1"
    litellm_api_key: SecretStr
    laya_base_url: str = "http://127.0.0.1:8000"
    laya_model: str = "multilingual"
    laya_min_confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    telegram_bot_token: SecretStr
    telegram_owner_user_id: int | None = None
    assistant_temp: float = 1
    specialist_temp: float = 0.3
    db_path: str = ""
    google_oauth_credentials: Path
    google_calendar_mcp_token_path: Path


    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

def get_settings():
    settings = Settings()
    return settings 
        


        

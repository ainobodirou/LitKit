from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from pathlib import Path
from functools import lru_cache

class Settings(BaseSettings):
    litellm_base_url: str = "http://localhost:4000/v1"
    litellm_api_key: SecretStr
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
        


        

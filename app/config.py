from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    litellm_base_url: str = "http://localhost:4000/v1"
    litellm_api_key: str
    telegram_bot_token: str
    telegram_owner_user_id: int | None = None
    assistant_temp: float = 0.2
    specialist_temp: float = 0.3

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

def get_settings():
    settings = Settings()
    return settings 
        


        

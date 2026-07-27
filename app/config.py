from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    litellm_base_url: str = "http://localhost:4000/v1"
    litellm_api_key: str
    telegram_bot_token: SecretStr
    telegram_owner_user_id: int | None = None


    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
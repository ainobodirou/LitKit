from dataclasses import dataclass
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import Settings 

@dataclass(frozen=True)
class AssistantModels:
    supervisor: BaseChatModel
    specialist: BaseChatModel

def create_assistant_models(settings: Settings) -> AssistantModels:
    common_options = {
        "base_url" : settings.litellm_base_url,
        "api_key" : settings.litellm_api_key.get_secret_value(),
        "timeout" : 60,
        "max_retries": 0
    }

    return AssistantModels(
        supervisor=ChatOpenAI(
            model = "assistant-supervisor",
            temperature = settings.assistant_temp,
            **common_options
        ),
        specialist = ChatOpenAI(
            model = "assistant-specialist",
            temperature = settings.specialist_temp,
            **common_options
        ),
    )

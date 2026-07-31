from dataclasses import dataclass

from app.assistant.service import AssistantService
from app.telegram.service import TelegramBotService
from app.telegram.app import create_application
from app.config import Settings
from app.llm.models import create_assistant_models

## bootstrap: creates runtime class that build all dependancies
## for assistant runtime

@dataclass(frozen = True)
class Runtime:
    assistant_service: AssistantService
    telegram_transport: TelegramBotService
    # Create model clients, assistant service, telegram application and transport
    def create_runtime(settings: Settings):

        models = create_assistant_models(settings)
        supervisor = models.supervisor

        assistant_service = AssistantService(supervisor = supervisor)

        telegram_app = create_application(
            token = settings.telegram_bot_token,
            assistant = assistant_service,
            owner_user_id = settings.telegram_owner_user_id,
        )

        telegram_transport = TelegramBotService(
            application=telegram_app
        )
        
        return Runtime(
            assistant_service=assistant_service,
            telegram_transport=telegram_transport
        )



import logging
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    BaseHandler,
    filters,
)

from app.assistant.service import AssistantService
from app.telegram.handlers import (
    create_start_handler,
    create_text_handler,
)

logger = logging.getLogger(__name__)

async def handle_error(
    update: object | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.error(
        "Unhandled Telegram update-processing error.",
        exc_info=context.error,
    )

def create_application(*, token:str, assistant: AssistantService, owner_user_id:int) -> Application:
    application = (
        Application.builder()
        .token(token)
        .build()
    )
    application.add_handler(
        CommandHandler(
            "start",
            create_start_handler(
                owner_user_id=owner_user_id,
                )
            ),
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            create_text_handler(
                assistant=assistant,
                owner_user_id=owner_user_id,
            ),
        )
    )
        
    application.add_error_handler(handle_error)

    return application

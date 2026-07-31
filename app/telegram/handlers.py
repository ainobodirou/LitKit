import logging 
from collections.abc import Awaitable, Callable 

from telegram import Update 
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.assistant.service import AssistantService 

logger = logging.getLogger(__name__)

HandlerCallback = Callable[
    [Update, ContextTypes.DEFAULT_TYPE],
    Awaitable[None]
]

def create_start_handler(owner_user_id: int) -> HandlerCallback:
    async def start(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = update.effective_user
        message = update.effective_message

        if user is None or message is None:
            return
        if user.id != owner_user_id:
            logger.warning("Unauthorizaed Telegram user:%s",
            user.id)
            return

        await message.reply_text(
            "LitKit is live"
        )
    return start
    
def create_text_handler(
        assistant: AssistantService,
        owner_user_id: int,
):
    async def handle_text(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        user = update.effective_user
        chat = update.effective_chat
        message = update.effective_message

        if user is None or chat is None or message is None:
            return
        if user.id != owner_user_id:
            logger.warning("Unauthorized Telegram user: %s", user.id)
            return
        if message.text is None:
            return
        await context.bot.send_chat_action(
            chat_id=chat.id,
            action = ChatAction.TYPING,
        )
        try: 
            response = await assistant.respond(
                user_id=str(user.id),
                conversation_id = str(chat.id),
                text = message.text,
            )
        except Exception:
            logger.exception("Assistant Failed")

            await message.reply_text(
                "Internal error encountered"
            )
            return
        await message.reply_text(response)
    return handle_text
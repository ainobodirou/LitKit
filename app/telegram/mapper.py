from telegram import Update
from app.telegram.contracts import UserMessage

def map_user_message(update: Update) -> UserMessage | None:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if (
        message is None
        or message.txt is None
        or user is None
        or chat is None
    ):
        return None
    return UserMessage(
        channel="telegram",
        sender_id = str(user.id),
        conversation_id=str(chat.id),
        text=message.text,

    )
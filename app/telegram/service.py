from telegram import Bot

from app.telegram.contracts import UserMessage, MessageSender

class TelegramService(MessageSender):
    def __init__(self,bot: Bot) -> None:
        self._bot = bot 

    async def send_text(self,*,recipient_id:str,text:str,) -> None:
        await self._bot.send_message(
            chat_id = int(recipient_id), ## dont like that conversion 
            text = text 
        )
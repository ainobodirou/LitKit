import logging
from telegram.ext import Application

logger = logging.getLogger(__name__)

class TelegramBotService:
    def __init__(
            self,
            *,
            application: Application
    ) -> None:
        self._application = application

    async def start(self) -> None:
        updater = self._application.updater

        if updater is None:
            raise RuntimeError(
                "Telegram Application has no updater"
            )
        
        await self._application.initialize()
        await updater.start_polling(
            drop_pending_updates=True,
        )
        await self._application.start()
        bot = self._application.bot
        logger.info(
            "Telegram bot started: @%s", bot.username,
        )
    async def stop(self) -> None:
        updater = self._application.updater

        if updater is not None and updater.running:
            await updater.stop()
        if self._application.running:
            await self._application.stop()
        await self._application.shutdown()
        logger.info("Telegram bot stopped.")


    
from dataclasses import dataclass
from app.assistant.prompts import CALENDAR_PROMPT, FALLBACK_PROMPT
from app.assistant.service import AssistantService
from app.assistant.dispatcher import WorkflowDispatcher

from app.telegram.service import TelegramBotService
from app.telegram.app import create_application

from app.assistant.agents import (
    CalendarTaskAgent,
    GeneralAgent,
)

from app.config import Settings
from app.llm.models import create_assistant_models
from app.llm.embeddings import TextEmbeddingService
from app.mcp.client import create_mcp_client

from app.context.models import TaskType
from app.context.resolver import ContextResolver
from app.context.policies import TASK_POLICIES

from app.storage.duckdb.db import DuckDBDatabase
from app.storage.duckdb.memories import DuckDBMemoryRepo

## bootstrap: creates runtime class that build all dependancies
## for assistant runtime

@dataclass(frozen = True)
class Runtime:
    assistant_service: AssistantService
    telegram_transport: TelegramBotService
    database: DuckDBDatabase
    # Create model clients, assistant service, telegram application and transport

    async def close(self) -> None:
        try:
            await self.telegram_transport.stop()
        finally:
            self.database.close()


def create_runtime(settings: Settings) -> Runtime:

    models = create_assistant_models(settings)
    supervisor = models.supervisor
    specialist = models.specialist
    mcp_client = create_mcp_client(settings)
    database = DuckDBDatabase(path=settings.db_path)
    memory_repo = DuckDBMemoryRepo(conn=database.conn)

    context_resolver = ContextResolver(
        planner_model = supervisor,
        embedding_service= TextEmbeddingService(),
        policies=TASK_POLICIES,
        memory_repo= memory_repo,
    )

    calendar_agent = CalendarTaskAgent(
        model = specialist,
        mcp_client = mcp_client,
        sys_prompt= CALENDAR_PROMPT,
    )

    general_agent = GeneralAgent(
        model = supervisor,
        sys_prompt= FALLBACK_PROMPT
    )

    dispatcher = WorkflowDispatcher(
        agents = {
        TaskType.CALENDAR: calendar_agent,
        TaskType.GENERAL_CHAT: general_agent
        }
    )

    assistant_service = AssistantService(
        context_resolver = context_resolver,
        dispatcher = dispatcher,
    )

    telegram_app = create_application(
        token = settings.telegram_bot_token.get_secret_value(),
        assistant = assistant_service,
        owner_user_id = settings.telegram_owner_user_id,
    )

    telegram_transport = TelegramBotService(
        application=telegram_app
    )

    return Runtime(
        assistant_service=assistant_service,
        telegram_transport=telegram_transport,
        database = database
    )



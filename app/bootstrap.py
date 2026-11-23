from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools

from app.assistant.graphs.child_factory import ChildFactory
from app.assistant.graphs.nodes import OrchestrationNodes, TaskConfiguration
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
from app.llm.types import ModelRole
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
    orchestration_nodes: OrchestrationNodes
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

    @asynccontextmanager
    async def open_calendar_tools() -> AsyncIterator[Sequence[BaseTool]]:
        async with mcp_client.session("calendar") as session:
            yield await load_mcp_tools(session)

    @asynccontextmanager
    async def open_chat_tools() -> AsyncIterator[Sequence[BaseTool]]:
        yield []

    task_registry = {
        TaskType.CALENDAR: TaskConfiguration(
            model_role=ModelRole.SPECIALIST,
            system_prompt=CALENDAR_PROMPT,
            open_tools=open_calendar_tools,
        ),
        TaskType.GENERAL_CHAT: TaskConfiguration(
            model_role=ModelRole.SUPERVISOR,
            system_prompt=FALLBACK_PROMPT,
            open_tools=open_chat_tools,
        ),
    }
    orchestration_nodes = OrchestrationNodes(
        task_registry=task_registry,
        child_factory=ChildFactory(),
    )

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
        database=database,
        orchestration_nodes=orchestration_nodes,
    )



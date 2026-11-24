from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app import bootstrap
from app.assistant.graphs import child_factory
from app.assistant.graphs.child_factory import ChildFactory
from app.assistant.graphs.sub_state import SubgraphState
from app.assistant.prompts import CALENDAR_PROMPT, FALLBACK_PROMPT
from app.config import Settings
from app.context.models import TaskType
from app.llm.types import ModelRole


def test_child_factory_forwards_agent_configuration(monkeypatch):
    runnable = Mock()
    create_agent = Mock(return_value=runnable)
    monkeypatch.setattr(child_factory, "create_agent", create_agent)
    model = Mock()
    tools = [Mock()]

    result = ChildFactory().build(model=model, tools=tools, system_prompt=CALENDAR_PROMPT)

    create_agent.assert_called_once_with(
        model=model,
        tools=tools,
        system_prompt=CALENDAR_PROMPT,
        state_schema=SubgraphState,
        middleware=[child_factory.include_feedback],
    )
    assert result is runnable


@pytest.mark.asyncio
async def test_runtime_injects_task_registry_with_lazy_calendar_tools(monkeypatch):
    events = []
    session = object()
    calendar_tools = [Mock(name="create_event")]

    @asynccontextmanager
    async def calendar_session():
        events.append("opened")
        try:
            yield session
        finally:
            events.append("closed")

    async def load_tools(active_session):
        assert active_session is session
        assert events == ["opened"]
        events.append("loaded")
        return calendar_tools

    open_session = Mock(side_effect=lambda name: calendar_session())
    load_mcp_tools = AsyncMock(side_effect=load_tools)
    models = SimpleNamespace(supervisor=Mock(), specialist=Mock())
    monkeypatch.setattr(bootstrap, "create_assistant_models", Mock(return_value=models))
    monkeypatch.setattr(
        bootstrap, "create_mcp_client", Mock(return_value=SimpleNamespace(session=open_session))
    )
    monkeypatch.setattr(bootstrap, "load_mcp_tools", load_mcp_tools)
    monkeypatch.setattr(bootstrap, "DuckDBDatabase", Mock())
    monkeypatch.setattr(bootstrap, "TextEmbeddingService", Mock())
    monkeypatch.setattr(bootstrap, "create_application", Mock())

    runtime = bootstrap.create_runtime(
        Settings(
            _env_file=None,
            litellm_api_key="unused",
            telegram_bot_token="unused",
            telegram_owner_user_id=1,
            google_oauth_credentials="unused-credentials.json",
            google_calendar_mcp_token_path="unused-token.json",
        )
    )

    open_session.assert_not_called()
    load_mcp_tools.assert_not_awaited()
    nodes = runtime.orchestration_nodes
    assert isinstance(nodes._child_factory, ChildFactory)
    assert set(nodes._task_registry) == {TaskType.CALENDAR, TaskType.GENERAL_CHAT}

    chat = nodes._task_registry[TaskType.GENERAL_CHAT]
    assert chat.model_role is ModelRole.SUPERVISOR
    assert chat.system_prompt == FALLBACK_PROMPT
    async with chat.open_tools() as tools:
        assert tools == []
    open_session.assert_not_called()

    calendar = nodes._task_registry[TaskType.CALENDAR]
    assert calendar.model_role is ModelRole.SPECIALIST
    assert calendar.system_prompt == CALENDAR_PROMPT
    async with calendar.open_tools() as tools:
        assert tools is calendar_tools
        assert events == ["opened", "loaded"]
    open_session.assert_called_once_with("calendar")
    load_mcp_tools.assert_awaited_once_with(session)
    assert events == ["opened", "loaded", "closed"]

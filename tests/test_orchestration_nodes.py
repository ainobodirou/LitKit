import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage
from pydantic import SecretStr, ValidationError

from app.assistant.graphs.child_factory import ChildFactory
from app.assistant.graphs.nodes import OrchestrationNodes
from app.assistant.graphs.orchestrator_state import PreparedContext, RetrievedContext
from app.context.models import ContextPacket, ContextPlan, ContextSource, RoutingContext, TaskType
from app.context.policies import TASK_POLICIES
from app.context.resolver import ContextResolver
from app.llm.models import AssistantModels, create_assistant_models


@pytest.fixture
def nodes():
    return OrchestrationNodes(task_registry={}, child_factory=Mock(spec=ChildFactory))


@pytest.fixture
def state():
    supervisor = Mock()
    specialist = Mock()
    orchestrator = Mock()
    orchestrator.with_structured_output.return_value.ainvoke = AsyncMock()
    distiller = Mock()
    distiller.ainvoke = AsyncMock()
    return {
        "ctx_packet": ContextPacket(
            task_type=TaskType.CALENDAR,
            model_role="specialist",
            current_request="Schedule the check-in on Friday.",
            recent_messages=("A previous message",),
            memories=(),
            allowed_resources=(ContextSource.USER_MEMORY,),
        ),
        "models": AssistantModels(supervisor, specialist, orchestrator, distiller),
        "max_attempts": 2,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [None, ()])
async def test_empty_scope_skips_model(nodes, state, scope):
    state["ctx_packet"].allowed_resources = scope

    assert await nodes.review_and_retrieve(state) == {}
    state["models"].orchestrator.with_structured_output.assert_not_called()


@pytest.mark.asyncio
async def test_review_sends_packet_fields_and_honors_skip(nodes, state):
    planner = state["models"].orchestrator.with_structured_output.return_value
    planner.ainvoke.return_value = {"action": "skip"}
    nodes.retrieve_helper = AsyncMock()

    assert await nodes.review_and_retrieve(state) == {}

    system, request = planner.ainvoke.await_args.args[0]
    assert "lookup" in system.content
    assert json.loads(request.content) == {
        "task_type": "calendar",
        "current_request": "Schedule the check-in on Friday.",
        "allowed_resources": ["user_memory"],
    }
    nodes.retrieve_helper.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_returns_helper_data(nodes, state):
    planner = state["models"].orchestrator.with_structured_output.return_value
    planner.ainvoke.return_value = {
        "action": "lookup",
        "source": "user_memory",
        "query": "  Preferred meeting time  ",
    }
    retrieved = RetrievedContext(ContextSource.USER_MEMORY, "Preferred meeting time", "10:00")
    nodes.retrieve_helper = AsyncMock(return_value=retrieved)

    assert await nodes.review_and_retrieve(state) == {"retrieved_context": retrieved}
    nodes.retrieve_helper.assert_awaited_once_with(
        ContextSource.USER_MEMORY, "Preferred meeting time"
    )


@pytest.mark.asyncio
async def test_allowed_lookup_records_empty_stub_result(nodes, state):
    planner = state["models"].orchestrator.with_structured_output.return_value
    planner.ainvoke.return_value = {
        "action": "lookup",
        "source": "user_memory",
        "query": "Preferred meeting time",
    }

    assert await nodes.review_and_retrieve(state) == {"retrieved_context": None}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"action": "lookup", "source": "knowledge", "query": "time"}, ValueError),
        ({"action": "lookup", "query": "time"}, ValueError),
        ({"action": "lookup", "source": "user_memory", "query": "   "}, ValueError),
        ({"action": "retrieve"}, ValidationError),
    ],
)
async def test_invalid_decisions_never_reach_retrieval(nodes, state, response, error):
    planner = state["models"].orchestrator.with_structured_output.return_value
    planner.ainvoke.return_value = response
    nodes.retrieve_helper = AsyncMock()

    with pytest.raises(error):
        await nodes.review_and_retrieve(state)
    nodes.retrieve_helper.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_at", ["model", "helper"])
async def test_review_propagates_errors(nodes, state, failure_at):
    planner = state["models"].orchestrator.with_structured_output.return_value
    planner.ainvoke.return_value = {
        "action": "lookup",
        "source": "user_memory",
        "query": "Preferred meeting time",
    }
    nodes.retrieve_helper = AsyncMock()
    failure = TimeoutError("timed out")
    call = planner.ainvoke if failure_at == "model" else nodes.retrieve_helper
    call.side_effect = failure

    with pytest.raises(TimeoutError) as exc:
        await nodes.review_and_retrieve(state)
    assert exc.value is failure


@pytest.mark.asyncio
@pytest.mark.parametrize("extra_bytes", [0, 1])
async def test_distill_budget_boundary_uses_utf8_bytes(nodes, state, extra_bytes):
    empty = json.dumps(
        asdict(PreparedContext("", None, None, ())),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    padding = 5_000 * 4 - len(empty.encode("utf-8")) + extra_bytes
    original = "é" * (padding // 2) + "a" * (padding % 2)
    state["ctx_packet"].current_request = original
    distiller = state["models"].distiller
    distiller.ainvoke.return_value = AIMessage(content="Compact request")

    update = await nodes.distill_context(state)

    assert distiller.ainvoke.await_count == extra_bytes
    expected = "Compact request" if extra_bytes else original
    assert update == {"prepared_context": PreparedContext(expected, None, None, ())}
    assert state["ctx_packet"].current_request == original


@pytest.mark.asyncio
@pytest.mark.parametrize("needs_request_compaction", [False, True])
async def test_distill_summarizes_retrieval_before_request(nodes, state, needs_request_compaction):
    request = "Schedule the check-in Friday at 10:00."
    request_padding = " Background." * 2_000 if needs_request_compaction else ""
    packet = state["ctx_packet"]
    packet.current_request = request + request_padding
    retrieved = RetrievedContext(ContextSource.USER_MEMORY, "time", "Past notes " * 2_000)
    state.update(retrieved_context=retrieved, feedback="Include the time.", tools=["create-event"])
    distiller = state["models"].distiller
    distiller.ainvoke.side_effect = [
        AIMessage(content="The user prefers 10:00."),
        AIMessage(content=request),
    ]

    update = await nodes.distill_context(state)

    assert update == {
        "prepared_context": PreparedContext(
            request,
            RetrievedContext(retrieved.source, retrieved.query, "The user prefers 10:00."),
            "Include the time.",
            ("create-event",),
        )
    }
    targets = [
        json.loads(call.args[0][-1].content)["target"]
        for call in distiller.ainvoke.await_args_list
    ]
    expected_targets = ["retrieved_context.text"]
    if needs_request_compaction:
        expected_targets.append("current_request")
    assert targets == expected_targets
    assert packet.current_request == request + request_padding
    assert state["retrieved_context"] is retrieved


@pytest.mark.asyncio
async def test_distill_returns_prepared_context_when_still_above_soft_budget(nodes, state):
    feedback = "Keep this exact. " * 2_000
    state["feedback"] = feedback
    state["models"].distiller.ainvoke.return_value = AIMessage(content="Schedule the check-in.")

    update = await nodes.distill_context(state)

    assert update == {
        "prepared_context": PreparedContext("Schedule the check-in.", None, feedback, ())
    }
    state["models"].distiller.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolver_uses_task_policy_scope_even_without_initial_retrieval(state):
    planner_model = Mock()
    planner_model.with_structured_output.return_value.ainvoke = AsyncMock(
        return_value=ContextPlan(task_type=TaskType.CALENDAR, sources=(), constraints=())
    )
    repo = Mock()
    resolver = ContextResolver(
        planner_model=planner_model,
        embedding_service=Mock(),
        policies=TASK_POLICIES,
        memory_repo=repo,
    )

    packet = await resolver.resolve(RoutingContext("Check my calendar.", (), (), ()))

    assert packet.allowed_resources == TASK_POLICIES[TaskType.CALENDAR].allowed_sources
    assert packet.memories == ()
    repo.find_relevant.assert_not_called()
    legacy_packet = ContextPacket.model_validate(
        state["ctx_packet"].model_dump(exclude={"allowed_resources"})
    )
    assert legacy_packet.allowed_resources is None


def test_model_factory_reuses_existing_clients_for_named_bindings():
    settings = SimpleNamespace(
        litellm_base_url="http://127.0.0.1:4000/v1",
        litellm_api_key=SecretStr("unused"),
        assistant_temp=1.0,
        specialist_temp=0.3,
    )

    models = create_assistant_models(settings)

    assert models.orchestrator is models.supervisor
    assert models.distiller is models.specialist

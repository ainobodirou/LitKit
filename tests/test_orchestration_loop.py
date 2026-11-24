import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.assistant.graphs.child_factory import ChildFactory
from app.assistant.graphs.nodes import OrchestrationNodes, TaskConfiguration
from app.assistant.graphs.orchestrator_state import EvaluationDecision
from app.assistant.graphs.sub_state import SubgraphState
from app.assistant.graphs.workflow import build_orchestrator_graph
from app.context.models import ContextPacket, TaskType
from app.llm.models import AssistantModels
from app.llm.types import ModelRole


@pytest.fixture
def run_setup():
    events = []
    inputs = []
    tool = Mock()
    tool.name = "list-events"
    extra_tool = Mock()
    extra_tool.name = "get-freebusy"

    @asynccontextmanager
    async def open_tools() -> AsyncIterator[list]:
        owner = asyncio.current_task()
        events.append("opened")
        try:
            yield [tool, extra_tool]
        finally:
            assert asyncio.current_task() is owner
            events.append("closed")

    async def invoke_child(child_input):
        if state["tools"]:
            assert events[0] == "opened" and "closed" not in events
        inputs.append(child_input)
        events.append("executed")
        reply = f"Candidate {len(inputs)}"
        return {"messages": [*child_input["messages"], AIMessage(content=reply)]}

    child = Mock()
    child.ainvoke = AsyncMock(side_effect=invoke_child)
    factory = Mock(spec=ChildFactory)
    factory.build.return_value = child
    nodes = OrchestrationNodes(
        task_registry={
            TaskType.CALENDAR: TaskConfiguration(
                ModelRole.SPECIALIST, "Calendar workflow", open_tools
            )
        },
        child_factory=factory,
    )
    evaluator = Mock()
    evaluator.evaluate = AsyncMock()
    models = AssistantModels(
        supervisor=Mock(),
        specialist=Mock(),
        orchestrator=Mock(),
        distiller=Mock(),
    )
    state = {
        "ctx_packet": ContextPacket(
            task_type=TaskType.CALENDAR,
            model_role="specialist",
            recent_messages=(),
            current_request="What events are scheduled for Friday?",
            memories=(),
        ),
        "models": models,
        "tools": ["list-events"],
        "feedback": None,
        "max_attempts": 3,
    }
    return state, nodes, evaluator, factory, tool, events, inputs


@pytest.mark.asyncio
async def test_repair_reuses_child_and_tool_session(run_setup):
    state, nodes, evaluator, factory, tool, events, inputs = run_setup

    async def evaluate(**kwargs):
        assert "closed" not in events
        events.append("evaluated")
        if len(inputs) == 1:
            return EvaluationDecision("repair", feedback="Include the timezone.")
        return EvaluationDecision("accept")

    evaluator.evaluate.side_effect = evaluate
    graph = build_orchestrator_graph(nodes, evaluator=evaluator)
    result = await graph.ainvoke(state)

    factory.build.assert_called_once_with(
        model=state["models"].specialist,
        tools=[tool],
        system_prompt="Calendar workflow",
        state_schema=SubgraphState,
    )
    assert events == ["opened", "executed", "evaluated", "executed", "evaluated", "closed"]
    assert [attempt["feedback"] for attempt in inputs] == [None, "Include the timezone."]
    assert inputs[1]["task_context"].feedback == "Include the timezone."
    assert result["prepared_context"].feedback is None
    assert result["feedback"] == "Include the timezone."
    assert result["max_attempts"] == 1
    assert result["reply"] == "Candidate 2"


@pytest.mark.asyncio
async def test_child_factory_puts_feedback_in_model_messages_once(run_setup):
    state, _, evaluator, _, _, _, _ = run_setup
    prompts = []

    class RecordPrompts(BaseCallbackHandler):
        def on_chat_model_start(self, serialized, messages, **kwargs):
            prompts.extend(messages)

    model = FakeListChatModel(
        responses=["First reply", "Corrected reply"], callbacks=[RecordPrompts()]
    )
    state["models"] = replace(state["models"], specialist=model)
    state["tools"] = []
    open_tools = Mock()
    nodes = OrchestrationNodes(
        task_registry={
            TaskType.CALENDAR: TaskConfiguration(
                ModelRole.SPECIALIST, "Calendar workflow", open_tools
            )
        },
        child_factory=ChildFactory(),
    )
    feedback = "Include the timezone."
    evaluator.evaluate.side_effect = [
        EvaluationDecision("repair", feedback=feedback),
        EvaluationDecision("accept"),
    ]

    result = await build_orchestrator_graph(nodes, evaluator=evaluator).ainvoke(state)

    human_messages = [
        [message.text for message in prompt if isinstance(message, HumanMessage)]
        for prompt in prompts
    ]
    assert len(human_messages) == 2
    assert all(feedback not in message for message in human_messages[0])
    assert human_messages[1].count(f"Evaluator feedback for this attempt:\n{feedback}") == 1
    assert result["reply"] == "Corrected reply"
    open_tools.assert_not_called()


@pytest.mark.asyncio
async def test_repair_stops_when_attempt_budget_reaches_zero(run_setup):
    state, nodes, evaluator, factory, _, events, inputs = run_setup
    state["max_attempts"] = 1
    evaluator.evaluate.return_value = EvaluationDecision("repair", feedback="Check accuracy.")

    result = await build_orchestrator_graph(nodes, evaluator=evaluator).ainvoke(state)

    assert result["verdict"] == "exhausted"
    assert result["max_attempts"] == 0
    assert result["feedback"] == "Check accuracy."
    assert result["reply"]
    assert len(inputs) == 1
    assert events == ["opened", "executed", "closed"]
    factory.build.assert_called_once()


@pytest.mark.asyncio
async def test_tool_session_closes_on_evaluator_exception(run_setup):
    state, nodes, evaluator, _, _, events, _ = run_setup
    evaluator.evaluate.side_effect = RuntimeError("Evaluation unavailable")

    with pytest.raises(RuntimeError, match="Evaluation unavailable"):
        await build_orchestrator_graph(nodes, evaluator=evaluator).ainvoke(state)

    assert events == ["opened", "executed", "closed"]


@pytest.mark.asyncio
async def test_zero_budget_never_builds_a_child(run_setup):
    state, nodes, evaluator, factory, _, events, _ = run_setup
    state["max_attempts"] = 0

    result = await build_orchestrator_graph(nodes, evaluator=evaluator).ainvoke(state)

    assert result["verdict"] == "exhausted"
    assert result["max_attempts"] == 0
    assert events == []
    factory.build.assert_not_called()
    evaluator.evaluate.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_tool_list_runs_child_without_opening_calendar(run_setup):
    state, nodes, evaluator, factory, _, events, _ = run_setup
    state["tools"] = []
    evaluator.evaluate.return_value = EvaluationDecision("accept")

    result = await build_orchestrator_graph(nodes, evaluator=evaluator).ainvoke(state)

    assert result["reply"] == "Candidate 1"
    assert factory.build.call_args.kwargs["tools"] == []
    assert events == ["executed"]


def calendar_write_messages(*receipts):
    tool_call = {"name": "create-event", "args": {}, "id": "write-1"}
    return {
        "messages": [
            AIMessage(content="", tool_calls=[tool_call]),
            *receipts,
            AIMessage(content="Calendar changed."),
        ]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "artifact"),
    [
        ('{"event":{"id":"google-123"}}', None),
        ("Event created", {"structured_content": {"event": {"id": "google-123"}}}),
    ],
)
async def test_confirmed_write_uses_evaluator_reply_without_running_child_again(
    run_setup, content, artifact
):
    state, nodes, evaluator, factory, tool, events, _ = run_setup
    state["tools"] = ["create-event"]
    tool.name = "create-event"
    receipt = ToolMessage(
        name="create-event", tool_call_id="write-1", content=content, artifact=artifact
    )
    child = factory.build.return_value
    child.ainvoke = AsyncMock(return_value=calendar_write_messages(receipt))
    evaluator.evaluate.return_value = EvaluationDecision(
        "repair", feedback="Include the event ID.", reply="Created event google-123."
    )

    result = await build_orchestrator_graph(nodes, evaluator=evaluator).ainvoke(state)

    assert result["verdict"] == "accept"
    assert result["reply"] == "Created event google-123."
    assert result["feedback"] == "Include the event ID."
    assert result["max_attempts"] == 2
    assert result["outcome"].tool_results == (receipt,)
    child.ainvoke.assert_awaited_once()
    evaluator.evaluate.assert_awaited_once()
    assert events == ["opened", "closed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("second_call_id", ["write-2", "write-1", ""])
async def test_one_unconfirmed_write_blocks_an_attempt_with_multiple_writes(
    run_setup, second_call_id
):
    state, nodes, evaluator, factory, tool, _, _ = run_setup
    state["tools"] = ["create-event"]
    tool.name = "create-event"
    child = factory.build.return_value
    result = calendar_write_messages(
        ToolMessage(
            name="create-event",
            tool_call_id="write-1",
            content='{"event":{"id":"google-123"}}',
        )
    )
    result["messages"][0].tool_calls.append(
        {"name": "create-event", "args": {}, "id": second_call_id}
    )
    child.ainvoke = AsyncMock(return_value=result)

    result = await build_orchestrator_graph(nodes, evaluator=evaluator).ainvoke(state)

    assert result["verdict"] == "blocked"
    assert result["max_attempts"] == 2
    child.ainvoke.assert_awaited_once()
    evaluator.evaluate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "receipts",
    [
        (),
        (ToolMessage(content='{"event":{"id":"other"}}', tool_call_id="write-other"),),
        (ToolMessage(content="Event ID is google-123", tool_call_id="write-1"),),
        (ToolMessage(
            content='{"event":{"id":"google-123"}}', tool_call_id="write-1", status="error"
        ),),
    ],
)
async def test_uncertain_write_stops_without_retry_or_evaluator(
    run_setup, receipts
):
    state, nodes, evaluator, factory, tool, events, _ = run_setup
    state["tools"] = ["create-event"]
    tool.name = "create-event"
    child = factory.build.return_value
    child.ainvoke = AsyncMock(return_value=calendar_write_messages(*receipts))

    result = await build_orchestrator_graph(nodes, evaluator=evaluator).ainvoke(state)

    assert result["verdict"] == "blocked"
    assert "couldn't confirm" in result["reply"]
    assert result["max_attempts"] == 2
    child.ainvoke.assert_awaited_once()
    evaluator.evaluate.assert_not_awaited()
    assert events == ["opened", "closed"]

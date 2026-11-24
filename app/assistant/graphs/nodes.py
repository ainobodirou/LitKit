import json
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext
from dataclasses import asdict, dataclass, replace
from typing import Literal, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolCall, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel

from app.assistant.graphs.IOrchestrationGraph import IOrchestrationGraph
from app.assistant.graphs.child_factory import ChildFactory
from app.assistant.graphs.orchestrator_state import (
    ChildOutcome,
    EvaluationDecision,
    OrchestratorState,
    PreparedContext,
    RetrievedContext,
)
from app.assistant.graphs.sub_state import SubgraphState
from app.assistant.prompts import CONTEXT_DISTILLATION_PROMPT, RETRIEVAL_DECISION_PROMPT
from app.context.models import ContextSource, TaskType
from app.llm.types import ModelRole

SOFT_TOKEN_BUDGET = 5_000
ESTIMATED_BYTES_PER_TOKEN = 4
CALENDAR_WRITE_TOOLS = frozenset({"create-event", "update-event", "respond-to-event"})

##Retrieval decision class for deciding on current context distillation
##Has only 1 consumer: exceeds_budget 

class RetrievalDecision(BaseModel):
    action: Literal["skip", "lookup"]
    source: ContextSource | None = None
    query: str | None = None

#Count payload tokens using conventional rule for ienglish prose: 4 characters per token 
#Needs calibration in v2 and handling other languages comparably

def exceeds_budget(context: PreparedContext) -> bool:
    payload = json.dumps(asdict(context), ensure_ascii=False, separators=(",", ":"))
    return len(payload.encode("utf-8")) > SOFT_TOKEN_BUDGET * ESTIMATED_BYTES_PER_TOKEN


async def _compact_text(
    model: BaseChatModel,
    context: PreparedContext,
    target: Literal["retrieved_context.text", "current_request"],
    original: str,
) -> str:
    payload = json.dumps(
        {"target": target, "context": asdict(context)},
        ensure_ascii=False,
    )
    response = await model.ainvoke(
        [
            SystemMessage(content=CONTEXT_DISTILLATION_PROMPT),
            HumanMessage(content=payload),
        ]
    )
    compacted = response.text.strip()
    if compacted and len(compacted.encode("utf-8")) < len(original.encode("utf-8")):
        return compacted
    return original


@dataclass(frozen=True)
class TaskConfiguration:
    model_role: ModelRole
    system_prompt: str
    open_tools: Callable[[], AbstractAsyncContextManager[Sequence[BaseTool]]]


class OutcomeEvaluator(Protocol):
    async def evaluate(
        self, *, request: str, outcome: ChildOutcome, feedback: str | None
    ) -> EvaluationDecision:
        """Evaluate one completed child attempt."""
        ...


@dataclass(frozen=True)
class AttemptRuntime:
    child: CompiledStateGraph
    evaluator: OutcomeEvaluator


def _confirms_calendar_write(result: ToolMessage) -> bool:
    if result.status != "success":
        return False

    payload = None
    if isinstance(result.artifact, Mapping):
        payload = result.artifact.get("structured_content")
    if payload is None:
        try:
            payload = json.loads(result.text)
        except json.JSONDecodeError:
            return False
    if not isinstance(payload, Mapping) or payload.get("error"):
        return False
    if payload.get("success") is False:
        return False
    event = payload.get("event")
    event_id = event.get("id") if isinstance(event, Mapping) else None
    return isinstance(event_id, str) and bool(event_id.strip())


def _all_calendar_writes_confirmed(
    calls: Sequence[ToolCall], results: Sequence[ToolMessage]
) -> bool:
    seen_ids: set[str] = set()
    for call in calls:
        call_id = call.get("id")
        if not call_id or call_id in seen_ids:
            return False
        seen_ids.add(call_id)
        matches = [result for result in results if result.tool_call_id == call_id]
        if len(matches) != 1:
            return False
        result = matches[0]
        if result.name not in (None, call["name"]) or not _confirms_calendar_write(result):
            return False
    return True


class OrchestrationNodes(IOrchestrationGraph):

    ##OrchestrationNodes: implements OrchestrationGraph interface, that defines signatures of 
    # methods needed by graph builder orchestration entry graph node.

    def __init__(
        self,
        *,
        task_registry: Mapping[TaskType, TaskConfiguration],
        child_factory: ChildFactory,
    ) -> None:
        self._task_registry = dict(task_registry)
        self._child_factory = child_factory

    ##(Optional LLM reasoning step) Review the context packet, enrich or skip based on model response
    async def review_and_retrieve(self, state: OrchestratorState) -> dict[str, object]:
        packet = state["ctx_packet"]
        allowed_resources = packet.allowed_resources
        if not allowed_resources:
            return {}

        model = state["models"].orchestrator.with_structured_output(
            RetrievalDecision,
            method="function_calling",
        )
        response = await model.ainvoke(
            [
                SystemMessage(content=RETRIEVAL_DECISION_PROMPT),
                HumanMessage(
                    content=json.dumps(
                        {
                            "task_type": packet.task_type.value,
                            "current_request": packet.current_request,
                            "allowed_resources": [source.value for source in allowed_resources],
                        },
                        ensure_ascii=False,
                    )
                ),
            ]
        )
        decision = RetrievalDecision.model_validate(response)
        if decision.action == "skip":
            return {}

        source = decision.source
        query = decision.query.strip() if decision.query else ""
        if source is None or source not in allowed_resources:
            raise ValueError("The proposed lookup source is outside the allowed resources.")
        if not query:
            raise ValueError("A lookup requires a nonempty query.")

        return {"retrieved_context": await self.retrieve_helper(source, query)}

    ## Helper method for document retrieval
    async def retrieve_helper(
        self, source: ContextSource, query: str
    ) -> RetrievedContext | None:
        """Placeholder for retrieving data from a validated source."""
        return None

    ## Distill the original context packet and retrieved context
    ## Compact the retrieved text by default
    ## On soft budget violation - compact the current request aswell
    
    async def distill_context(self, state: OrchestratorState) -> dict[str, object]:
        retrieved = state.get("retrieved_context")
        prepared = PreparedContext(
            current_request=state["ctx_packet"].current_request,
            retrieved_context=retrieved,
            feedback=state.get("feedback"),
            tool_ids=tuple(state.get("tools", ())),
        )
        if not exceeds_budget(prepared):
            return {"prepared_context": prepared}

        model = state["models"].distiller
        if retrieved and retrieved.text:
            compacted = await _compact_text(
                model, prepared, "retrieved_context.text", retrieved.text
            )
            prepared = replace(prepared, retrieved_context=replace(retrieved, text=compacted))

        if exceeds_budget(prepared):
            compacted = await _compact_text(
                model, prepared, "current_request", prepared.current_request
            )
            prepared = replace(prepared, current_request=compacted)

        return {"prepared_context": prepared}

    @asynccontextmanager
    async def create_child(
        self, state: OrchestratorState
    ) -> AsyncIterator[CompiledStateGraph]:
        task_type = state["ctx_packet"].task_type
        configuration = self._task_registry[task_type]
        model = getattr(state["models"], configuration.model_role.value)
        approved_tools = set(state["tools"])
        tool_scope = configuration.open_tools() if approved_tools else nullcontext(())
        async with tool_scope as tools:
            yield self._child_factory.build(
                model=model,
                tools=[tool for tool in tools if tool.name in approved_tools],
                system_prompt=configuration.system_prompt,
                state_schema=SubgraphState,
            )

    async def execute_subgraph(
        self, state: OrchestratorState, runtime: Runtime[AttemptRuntime]
    ) -> dict[str, object]:
        prepared = replace(state["prepared_context"], feedback=state.get("feedback"))
        sections = [f"User request:\n{prepared.current_request}"]
        if prepared.retrieved_context:
            sections.append(f"Retrieved context:\n{prepared.retrieved_context.text}")
        previous = state.get("outcome")
        if previous:
            sections.append(f"Previous candidate reply:\n{previous.candidate_reply}")
            if previous.tool_results:
                results = "\n".join(
                    f"{receipt.name}: {receipt.text}" for receipt in previous.tool_results
                )
                sections.append(f"Previous tool results:\n{results}")

        child_input: SubgraphState = {
            "messages": [HumanMessage(content="\n\n".join(sections))],
            "task_context": prepared,
            "feedback": prepared.feedback,
        }
        result = await runtime.context.child.ainvoke(child_input)
        messages = result["messages"]
        outcome = ChildOutcome(
            candidate_reply=next(
                (
                    message.text
                    for message in reversed(messages)
                    if isinstance(message, AIMessage)
                    and not message.tool_calls
                    and message.text
                ),
                "",
            ),
            tool_calls=tuple(
                call
                for message in messages
                if isinstance(message, AIMessage)
                for call in message.tool_calls
            ),
            tool_results=tuple(
                message for message in messages if isinstance(message, ToolMessage)
            ),
        )
        return {"outcome": outcome, "max_attempts": state["max_attempts"] - 1}

    async def evaluate(
        self, state: OrchestratorState, runtime: Runtime[AttemptRuntime]
    ) -> dict[str, object]:
        outcome = state["outcome"]
        packet = state["ctx_packet"]
        write_calls = [
            call for call in outcome.tool_calls
            if packet.task_type == TaskType.CALENDAR and call["name"] in CALENDAR_WRITE_TOOLS
        ]
        if not _all_calendar_writes_confirmed(write_calls, outcome.tool_results):
            return {
                "verdict": "blocked",
                "reply": "I couldn't confirm the calendar change. Check your calendar before trying again.",
            }

        decision = await runtime.context.evaluator.evaluate(
            request=packet.current_request,
            outcome=outcome,
            feedback=state.get("feedback"),
        )
        if decision.verdict == "accept":
            return {"verdict": "accept", "reply": decision.reply or outcome.candidate_reply}

        update: dict[str, object] = {"verdict": decision.verdict}
        if decision.feedback is not None:
            update["feedback"] = decision.feedback

        if decision.verdict == "repair":
            if write_calls:
                if decision.reply and decision.reply.strip():
                    update.update(verdict="accept", reply=decision.reply)
                else:
                    update.update(
                        verdict="blocked",
                        reply="The calendar change completed, but I couldn't produce a verified summary.",
                    )
            elif state["max_attempts"] == 0:
                update.update(
                    verdict="exhausted",
                    reply=decision.reply or "I couldn't complete the request within the attempt limit.",
                )
            return update

        if decision.verdict == "needs_input":
            update["reply"] = decision.reply or "Could you clarify what you'd like me to do?"
        else:
            update["reply"] = decision.reply or "I couldn't complete the request."
        return update

import json
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass, replace
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from app.assistant.graphs.IOrchestrationGraph import IOrchestrationGraph
from app.assistant.graphs.child_factory import ChildFactory
from app.assistant.graphs.orchestrator_state import (
    OrchestratorState,
    PreparedContext,
    RetrievedContext,
)
from app.assistant.prompts import CONTEXT_DISTILLATION_PROMPT, RETRIEVAL_DECISION_PROMPT
from app.context.models import ContextSource, TaskType
from app.llm.types import ModelRole

SOFT_TOKEN_BUDGET = 5_000
ESTIMATED_BYTES_PER_TOKEN = 4

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

from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict

from langchain_core.messages import ToolCall, ToolMessage

from app.context.models import ContextPacket, ContextSource
from app.llm.models import AssistantModels


@dataclass(frozen=True)
class RetrievedContext:
    source: ContextSource
    query: str
    text: str


@dataclass(frozen=True)
class PreparedContext:
    current_request: str
    retrieved_context: RetrievedContext | None
    feedback: str | None
    tool_ids: tuple[str, ...]


@dataclass(frozen=True)
class ChildOutcome:
    candidate_reply: str
    tool_calls: tuple[ToolCall, ...]
    tool_results: tuple[ToolMessage, ...]


@dataclass(frozen=True)
class EvaluationDecision:
    verdict: Literal["accept", "repair", "needs_input", "blocked"]
    feedback: str | None = None
    reply: str | None = None


class OrchestratorState(TypedDict):
    ctx_packet: ContextPacket ##reference to downstream context packet
    models: AssistantModels ## catalogue of models ( dataclass defined in llm/models)
    tools: list[str] ## list of tools
    feedback: str | None ## lates feedback
    max_attempts: int
    retrieved_context: NotRequired[RetrievedContext | None]
    prepared_context: NotRequired[PreparedContext]
    outcome: NotRequired[ChildOutcome]
    verdict: NotRequired[Literal["accept", "repair", "needs_input", "blocked", "exhausted"]]
    reply: NotRequired[str]


## Define Nodes 

##Data Step - review ctx_packet and retrieve data from allowed resources scope if neccessary
##LLM step - distill context packet once data and context is there
# ^^ Select the fields through filter, only use LLM if input is large! 
# ^^ RE-USE ON CONSECUTIVE RETRIES!!!

##Construct State for Subgraph (or subgraph will construct its own?)
##Action step - call and execute SubGraph, await 
## LLM step - check retires > evaluate response, response  Good? [Y/N]
# Y: Action step -> distill worklog (external service su dumb model can be used) and store 
#    LLM step -> respond to user               
# N: spend retry, provide feedback, re-run 
# Retries gone?
#    LLM step -> respond to user with feedback question
#             -> distill worklog, store with feedback      
# 
#                                                       





# Build orchestrator graph 


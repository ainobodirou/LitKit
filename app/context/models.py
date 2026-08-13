from dataclasses import dataclass
from enum import Enum 
from datetime import datetime 
from typing import Generic, Mapping, TypeVar
from llm.types import ModelType

class ContextSource: 
    RECENT_MESSAGES = "recent_messages"
    ACTIVE_TASK = "active_task"
    USER_MEMORY = "user_memory"



from dataclasses import dataclass
from enum import Enum



class TaskType(str, Enum):
    GENERAL_CHAT = "general_chat"
    WORKOUT_LOG = "workout_log"
    FITNESS_ADVICE = "fitness_advice"
    CALENDAR = "calendar"
    RESEARCH = "research"


class ContextSource(str, Enum):
    RECENT_MESSAGES = "recent_messages"
    ACTIVE_TASK = "active_task"
    USER_MEMORY = "user_memory"
    RECENT_EVENTS = "recent_events"
    KNOWLEDGE = "knowledge"
    EXTERNAL_STATE = "external_state"



@dataclass(frozen=True)
class TaskContextPolicy:
    task_type: TaskType
    sources: tuple[ContextSource, ...]
    max_memories: int = 0
    max_events: int = 0
    max_sources: int = 0
    model_role: str = "supervisor"

@dataclass(frozen=True)
class RoutingContext:
    current_request: str
    recent_messages: tuple[str,...]
    active_tasks: tuple[str,...]
    available_sources: tuple[str,...]


@dataclass(frozen = True)
class ContextPlan:
    task_type: str
    sources: tuple[str,...]
    capabilities: tuple[str,...]
    queries: tuple[str,...]
    constraints: tuple[str,...]
    model_role: str

@dataclass(frozen=True)
class ApprovedContextPlan:
    task_type: str
    sources: tuple[str,...]
    capabilities: tuple[str,...]
    model_type: ModelType
    
    max_memories: int = 0
    max_events: int = 0 
    max_sources: int = 0


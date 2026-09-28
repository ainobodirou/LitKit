from dataclasses import dataclass, field
from enum import Enum 
from datetime import datetime 

from pydantic import BaseModel


@dataclass(frozen=True)
class Memory:
    id: str
    content: str
    type: str
    created_at: datetime
    relevance: float | None = None 
    source_id: str | None = None


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
    allowed_sources: tuple[ContextSource, ...]
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

class ContextPacket(BaseModel):
    task_type:str
    model_role:str
    recent_messages:tuple[str,...]
    current_request: str
    memories: tuple[Memory,...]


class ContextPlan(BaseModel):
    task_type: str
    sources: tuple[str,...]
    constraints: tuple[str,...]

@dataclass(frozen=True)
class ApprovedContextPlan:
    task_type: str
    sources: tuple[str,...]
    model_role: str
    
    max_memories: int = 0
    max_events: int = 0 
    max_sources: int = 0




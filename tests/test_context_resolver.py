import pytest
from datetime import datetime, timezone

import pytest

from app.context.models import(
    ContextPlan,
    RoutingContext,
    ApprovedContextPlan,
    ContextSource,
    Memory,
    TaskType,
)
from langchain_core.language_models.chat_models import BaseChatModel
from app.context.policies import TASK_POLICIES
from app.context.resolver import ContextResolver

class FakePlanner:
    def __init__(self, plan: ContextPlan) -> None:
        self.plan = plan


    async def ainvoke(self, messages: object) -> ContextPlan:
        return self.plan

    def with_structured_output(self, context_plan: ContextPlan, include_raw: bool):
        return self

class DummyRepo:
    def __init__(self, memories: tuple[Memory,...]) -> None:
        self.memories = memories


    async def find_relevant(self, *, query: str, limit: int) -> tuple[Memory,...]:
        return self.memories

@pytest.mark.asyncio
async def test_resolver():
    #create 6 objects:
    memory = Memory(
        content="User preferes morning workouts",
        type = "preference",
        created_at=datetime(2002,10,6,12,00,00),
        relevance=0.9,
        source_id="src1"
    )

    fakerepo = DummyRepo((memory,))

    plan = ContextPlan(
        task_type = TaskType.GENERAL_CHAT,
        sources = (ContextSource.RECENT_MESSAGES,ContextSource.USER_MEMORY)
        constraints=()

    )

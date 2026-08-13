from app.context.models import (ContextPlan, 
                                TaskContextPolicy,
                                ApprovedContextPlan, 
                                TaskType, 
                                RoutingContext,
                                ContextPacket)

from app.context.policies import TASK_POLICIES

from langchain_core.language_models.chat_models import BaseChatModel
from collections.abc import Mapping 


class ContextResolver:
    def __init__(
            self,
            *,
            planner_model: BaseChatModel,
            policies: Mapping[
                TaskType,
                TaskContextPolicy,
            ],
            ) -> None:
        
        self._planner_model = planner_model
        self._policies = policies

    async def resolve(self,routing_context: RoutingContext) -> ContextPacket:

        plan = await self._plan(routing_context)
        approved_plan = self._approve(plan)
        context_packet = await self._build_context(
            routing_context,
            approved_plan,
        )

        return context_packet
        
    async def _plan(self, routing_context: RoutingContext) -> ContextPlan:
        pass

    async def _build_context(self, routing_context: RoutingContext, plan: ApprovedContextPlan)-> ContextPacket:
        pass

    def _approve(self, plan) -> ApprovedContextPlan:

        task = plan.task_type

        if task not in self._policies:
            raise ValueError(f"No policy defined for {task}")
        
        policy = self._policies

        if not set(plan.sources).issubset(policy.allowed_sources):
            raise ValueError("Requested sources out of task scope")
        if not set(plan.capabilities).issubset(policy.allowed_capabilities):
            raise ValueError("Requested capabilities out of task scope")
        
        return ApprovedContextPlan(

            task_type=task,
            sources = plan.sources,
            capabilities=plan.capabilities,
            model_role = policy.model_role,

            max_memories= policy.max_memories,
            max_events = policy.max_events,
            max_sources = policy.max_sources,
        )
        
        
        
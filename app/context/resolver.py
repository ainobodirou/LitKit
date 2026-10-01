from app.context.models import (ContextPlan, 
                                ContextSource,
                                TaskContextPolicy,
                                ApprovedContextPlan, 
                                TaskType, 
                                RoutingContext,
                                ContextPacket)
from app.context.repositories import MemoryRepo
from app.assistant.prompts import CONTEXT_PLANNER_PROMPT
from app.llm.embeddings import TextEmbeddingService, EmbeddingService
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import(
    HumanMessage,
    SystemMessage
)
from collections.abc import Mapping 

## Context packet is a finalized, defined and structured context model that the agent workflow receives beased on user query
## Context packet cannot be changed within its own workflow runtime.
## Context Resolver
## Enforces structured planning of context packet object creation from query to > task identification > policy alignment 
## > context planning > context packet creation 


class ContextResolver:
    def __init__(
            self,
            *,
            planner_model: BaseChatModel,
            embedding_service: EmbeddingService,
            policies: Mapping[
                TaskType,
                TaskContextPolicy,
            ],
            memory_repo: MemoryRepo
            ) -> None:
        
        self._planner_model = planner_model
        self.struct_planner = planner_model.with_structured_output(
            ContextPlan,
            method="function_calling",
            include_raw=False,
        )
        self._embedding_service = embedding_service
        self._policies = policies
        self.memory_repo = memory_repo


    async def resolve(self,routing_context: RoutingContext) -> ContextPacket:

        plan = await self._plan(routing_context)
        approved_plan = self._approve(plan)
        context_packet = await self._build_context(
            routing_context,
            approved_plan,
        )
        return context_packet

       
        
    async def _plan(self, routing_context: RoutingContext) -> ContextPlan:

        result = await self.struct_planner.ainvoke(
            [
                SystemMessage(
                    content=CONTEXT_PLANNER_PROMPT,
                ),
                HumanMessage(
                    content = f"""
                    Current request:
                    {routing_context.current_request}
                    Recent Messages:
                    {routing_context.recent_messages}
                    Active Tasks:
                    {routing_context.active_tasks}
                    """
                ),
            ]
        )
        return result
        
        

    async def _build_context(self, routing_context: RoutingContext, approved_plan: ApprovedContextPlan)-> ContextPacket:

        if ContextSource.RECENT_MESSAGES in approved_plan.sources:
            recent_messages = routing_context.recent_messages
        else:
            recent_messages = ()
        if ContextSource.USER_MEMORY in approved_plan.sources:
            query_embedding = await self._embedding_service.embed_query(text = routing_context.current_request)
            memories = await self.memory_repo.find_relevant(embedding_model = self._embedding_service.model_name,
                                                            query_embedding = query_embedding,
                                                            limit = approved_plan.max_memories)

        else:
            memories = ()
        return ContextPacket(
            task_type = approved_plan.task_type,
            model_role = approved_plan.model_role,
            recent_messages = recent_messages,
            current_request = routing_context.current_request,
            memories=memories
        )


        
        

    def _approve(self, plan) -> ApprovedContextPlan:

        task = plan.task_type

        if task not in self._policies:
            raise ValueError(f"No policy defined for {task}")
        
        policy = self._policies[task]

        if not set(plan.sources).issubset(policy.allowed_sources):
            raise ValueError("Requested sources out of task scope")
        
        return ApprovedContextPlan(

            task_type=task,
            sources = plan.sources,
            model_role = policy.model_role,

            max_memories= policy.max_memories,
            max_events = policy.max_events,
            max_sources = policy.max_sources,
        )
        
        
        

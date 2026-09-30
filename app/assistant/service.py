from app.context.resolver import ContextResolver
from app.assistant.dispatcher import WorkflowDispatcher
from app.context.models import RoutingContext, ContextPacket

## Assistant Service - routing of context packets and request into agent workflow and respond.
class AssistantService:
    def __init__ (self,
                   *,
                   context_resolver: ContextResolver,
                   dispatcher: WorkflowDispatcher,
                   ) -> None:
        self._context_resolver = context_resolver
        self._dispatcher = dispatcher


    ## Resolve request into ContextPacket ## 
    async def _context_route(self, *, user_id, conversation_id: str, text: str,) -> ContextPacket:
        routing_context = RoutingContext(
            current_request=text,
            recent_messages=(),
            active_tasks=(),
            available_sources=(),
        )
        return await self._context_resolver.resolve(routing_context)

    ## Dispatch ContextPacket into appropriate workflow ## 
    async def _packet_dispatch(self, *, user_id: str, conversation_id: str, text: str,) -> str:
        packet = await self._context_route(user_id=user_id, conversation_id=conversation_id,text=text)
        return await self._dispatcher.dispatch(packet)

    ## Request gateway method - receive, dispatch, respond ##
    async def respond(
        self,
        *,
        user_id: str,
        conversation_id: str,
        text: str,
    ) -> str:
        return await self._packet_dispatch(
            user_id=user_id,
            conversation_id=conversation_id,
            text=text,
        )

 
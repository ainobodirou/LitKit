from app.assistant.prompts import SUPERVISOR_PROMPT, SYSTEM_PROMPT
from app.context.resolver import ContextResolver
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

## Assistant Service - routing of context packets and request into agent workflow and respond.
class AssistantService:
    def __init__ (self,
                   *,
                   context_resolver: ContextResolver,
                   dispatcher: WorkflowDispatcher,
                   ) -> None:
        self._context_resolver = context_resolver
        self._dispatcher = dispatcher

    


    ## Assistant Service is solely a communication tool independend of the specific caller
    async def respond(
            self,
            *,
            user_id: str,
            conversation_id: str,
            text: str,
    ) -> str:
        response = await self._supervisor.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content = text),
            ]
        )
        content = response.content

        if isinstance(content,str):
            return content
        ## Some models can return output in other structures list/dict, needs parsing: #
        if isinstance(content, list):
            text_parts: list[str] = []

            for part in content:
                if isinstance(part,str):
                    text_parts.append(part)
                    continue

                if isinstance(part, dict):
                    part_text = part.get("text")
                    if isinstance(part_text, str):
                        text_parts.append(part_text)
            if text_parts:
                return ''.join(text_parts)
        raise RuntimeError("Model: no text returned")

 
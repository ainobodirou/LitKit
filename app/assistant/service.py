from app.assistant.prompts import SUPERVISOR_PROMPT, SYSTEM_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

## Assistant Service - handles incoming messages to langchain workflow ##

class AssistantService:
    def __init__ (self,
                   *,
                   supervisor: BaseChatModel,
                   ) -> None:
        self._supervisor = supervisor

    async def respond(
            self,
            *,
            user_ud: str,
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
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.language_models import BaseChatModel
from app.context.models import ContextPacket

## Fallback Agents 

class GeneralAgent():
    def __init__(
            self,
            *,
            model: BaseChatModel,
            sys_prompt: str,
    ) -> None:

        self._model = model
        self._sys_pormpt = sys_prompt

    async def run(self, packet: ContextPacket)-> str:
        agent = create_agent(
            model = self._model,
            system_prompt=self._sys_pormpt,
        )
        result = await agent.ainvoke(
            {
                'messages':[
                    HumanMessage(content=packet.current_request),
                    ]
            })
        return result["messages"][-1].text
        
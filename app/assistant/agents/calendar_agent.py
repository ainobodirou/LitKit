from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from app.context.models import ContextPacket


class CalendarTaskAgent:
    def __init__(
            self,
            *,
            model: BaseChatModel,
            mcp_client: MultiServerMCPClient,
            sys_prompt: str

    ) -> None:
        self._model = model
        self._mcp_client = mcp_client
        self._sys_prompt = sys_prompt

    async def run(self, packet: ContextPacket) -> str:
        sections = [
            ("Current resuts", packet.current_request.strip()),
            ("Recent messages", "\n".join(packet.recent_messages)),
            ("Relevant memories", "\n".join(memory.content for memory in packet.memories)),
        ]
        content = "\n\n".join(
        f"{label}:\n{value}"
        for label, value in sections
        if value
        )

        async with self._mcp_client.session("calendar") as session:
            tools = await load_mcp_tools(session)
            agent = create_agent(model = self._model,
                                tools = tools,
                                system_prompt = self._sys_prompt,
                                )
            result = await agent.ainvoke({
                "messages": [
                    HumanMessage(content = content),
                ]
            })
            return result["messages"][-1].text
            

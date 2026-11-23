from collections.abc import Sequence

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph


class ChildFactory:
    def build(
        self,
        *,
        model: BaseChatModel,
        tools: Sequence[BaseTool],
        system_prompt: str,
    ) -> CompiledStateGraph:
        return create_agent(model=model, tools=tools, system_prompt=system_prompt)

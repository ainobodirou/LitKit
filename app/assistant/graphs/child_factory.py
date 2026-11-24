from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import before_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from app.assistant.graphs.sub_state import SubgraphState


@before_agent(state_schema=SubgraphState)
async def include_feedback(
    state: SubgraphState, runtime: Runtime
) -> dict[str, object] | None:
    feedback = state.get("feedback")
    if feedback:
        return {
            "messages": [
                HumanMessage(content=f"Evaluator feedback for this attempt:\n{feedback}")
            ]
        }
    return None


class ChildFactory:
    def build(
        self,
        *,
        model: BaseChatModel,
        tools: Sequence[BaseTool],
        system_prompt: str,
        state_schema: type[SubgraphState] = SubgraphState,
    ) -> CompiledStateGraph:
        return create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            state_schema=state_schema,
            middleware=[include_feedback],
        )

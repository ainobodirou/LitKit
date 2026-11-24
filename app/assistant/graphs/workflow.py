from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.assistant.graphs.IOrchestrationGraph import IOrchestrationGraph
from app.assistant.graphs.nodes import AttemptRuntime, OutcomeEvaluator
from app.assistant.graphs.orchestrator_state import OrchestratorState


def build_orchestrator_graph(
    nodes: IOrchestrationGraph, *, evaluator: OutcomeEvaluator
) -> CompiledStateGraph:
    def after_evaluation(state: OrchestratorState) -> Literal["execute_subgraph", "__end__"]:
        if state["verdict"] == "repair" and state["max_attempts"] > 0:
            return "execute_subgraph"
        return END

    loop_builder = StateGraph(OrchestratorState, context_schema=AttemptRuntime)
    loop_builder.add_node("execute_subgraph", nodes.execute_subgraph)
    loop_builder.add_node("evaluate", nodes.evaluate)
    loop_builder.add_edge(START, "execute_subgraph")
    loop_builder.add_edge("execute_subgraph", "evaluate")
    loop_builder.add_conditional_edges("evaluate", after_evaluation)
    loop = loop_builder.compile()

    async def run_attempts(state: OrchestratorState) -> dict[str, object]:
        if state["max_attempts"] <= 0:
            return {
                "verdict": "exhausted",
                "reply": "I couldn't start the task because no attempts were available.",
            }

        async with nodes.create_child(state) as child:
            result = await loop.ainvoke(state, context=AttemptRuntime(child, evaluator))

        return {
            key: result[key]
            for key in ("outcome", "max_attempts", "verdict", "feedback", "reply")
            if key in result
        }

    builder = StateGraph(OrchestratorState)
    builder.add_node("review_and_retrieve", nodes.review_and_retrieve)
    builder.add_node("distill_context", nodes.distill_context)
    builder.add_node("run_attempts", run_attempts)

    builder.add_edge(START, "review_and_retrieve")
    builder.add_edge("review_and_retrieve", "distill_context")
    builder.add_edge("distill_context", "run_attempts")
    builder.add_edge("run_attempts", END)
    return builder.compile()

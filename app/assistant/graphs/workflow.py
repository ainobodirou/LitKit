from langgraph.graph import END, START, StateGraph

from app.assistant.graphs.IOrchestrationGraph import IOrchestrationGraph
from app.assistant.graphs.nodes import OrchestrationNodes
from app.assistant.graphs.orchestrator_state import OrchestratorState

def build_orchestrator_graph(nodes: IOrchestrationGraph):
    builder = StateGraph(OrchestratorState)

    builder.add_node("review_and_retrieve", nodes.review_and_retrieve)
    builder.add_node("distill_context", nodes.distill_context)

    builder.add_edge(START, "review_and_retrieve")
    builder.add_edge("review_and_retrieve", "distill_context")
    builder.add_edge("distill_context", END)
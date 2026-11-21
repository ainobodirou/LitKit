from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from graphs.state.orchestrator_state import OrchestratorState;
from graphs.IOrchestrationGraph import IOrchestrationGraph;

generalWorkflow = StateGraph(OrchestratorState)

generalWorkflow.add_node("review_and_retrieve", IOrchestrationGraph.review_and_retrieve)

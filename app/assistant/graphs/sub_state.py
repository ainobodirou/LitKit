from langchain.agents import AgentState

from app.assistant.graphs.orchestrator_state import PreparedContext

class SubgraphState(AgentState):
    task_context: PreparedContext
    feedback: str | None



## Define nodes 


## Build Subgraph

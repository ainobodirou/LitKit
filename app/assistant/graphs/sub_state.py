from assistant.graphs.nodes import PreparedContext
from langgraph.graph import MessagesState
from llm.models import AssistantModels

class SubgraphState(MessagesState):
    task_context: PreparedContext
    approved_tools: list[str]
    messages: MessagesState
    model: AssistantModels


## Define nodes 


## Build Subgraph
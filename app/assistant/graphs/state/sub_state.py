from context.models import ContextPacket
from langgraph.graph import MessagesState

class SubgraphState(MessagesState):
    task_context: ContextPacket
    approved_tools: list[str]
    messages: list[str]


## Define nodes 


## Build Subgraph
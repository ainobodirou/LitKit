from collections.abc import Callable, Mapping
from app.context.models import ContextPacket, TaskType
from app.assistant.agents.base import WorkflowAgent


## V.2 -> Introduce request-specific mutable agent state through
## rutnime factories.
WorkflowFactory = Callable[[], WorkflowAgent]
## V.2

class WorkflowDispatcher:
    def __init__(
            self,
            *,
            agents: Mapping[TaskType, WorkflowAgent],   
        ) -> None:
            self._agents = dict(agents)


    async def dispatch(self, packet: ContextPacket) -> str:
        try:
            agent = self._agents[packet.task_type]
        except KeyError as exc:
            raise ValueError(f"No agent registered for {packet.task_type}")

        return await agent.run(packet)
        
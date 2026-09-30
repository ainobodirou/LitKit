from typing import Protocol
from app.context.models import ContextPacket

class WorkflowAgent(Protocol):
    async def run(self, packet: ContextPacket) -> str:
        """Execute the agent workflow using an approved  context packet."""
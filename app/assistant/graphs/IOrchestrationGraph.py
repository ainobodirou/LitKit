from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.assistant.graphs.state.orchestrator_state import OrchestratorState


class IOrchestrationGraph(Protocol):
    """Node contracts for the parent orchestration graph.

    Each node returns the state fields it updates.
    """

    async def review_and_retrieve(self, state: OrchestratorState) -> dict[str, object]:
        """Review the context packet and retrieve any additional approved data."""
        ...

    async def distill_context(self, state: OrchestratorState) -> dict[str, object]:
        """Prepare the context needed for the current attempt."""
        ...

    async def execute_subgraph(self, state: OrchestratorState) -> dict[str, object]:
        """Build the child input, await one attempt, and return its outcome."""
        ...

    async def evaluate(self, state: OrchestratorState) -> dict[str, object]:
        """Assess the outcome and record the verdict and any repair feedback."""
        ...

    async def distill_and_store_worklog(
        self, state: OrchestratorState
    ) -> dict[str, object]:
        """Compact and persist the task outcome and relevant feedback."""
        ...

    async def respond(self, state: OrchestratorState) -> dict[str, object]:
        """Produce the user-facing reply or clarification question."""
        ...

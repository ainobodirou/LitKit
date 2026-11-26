import httpx
from pydantic import ValidationError

from app.context.classifier import LayaOutput
from app.context.models.context import RoutingContext


class LayaClassifier:
    def __init__(
        self, client: httpx.AsyncClient, *, model: str, min_confidence: float
    ) -> None:
        self._client = client
        self._model = model
        self._min_confidence = min_confidence

    async def classify(self, routing_context: RoutingContext) -> LayaOutput:
        questions = {
            "intent": {
                "type": "choice",
                "instructions": "Which workflow should handle the latest user request?",
                "criteria": {
                    "general_chat": "General conversation or a non-calendar request.",
                    "calendar": "Read or change the user's calendar or events.",
                    "uncertain": "The request lacks enough information to pick a workflow.",
                },
            },
            "use_recent_messages": {
                "type": "noul",
                "instructions": "Would recent messages help interpret the latest request?",
            },
            "use_user_memory": {
                "type": "noul",
                "instructions": "Would stored facts or preferences about the user help with this request?",
            },
        }
        if routing_context.active_tasks:
            questions["continues_active_task"] = {
                "type": "noul",
                "instructions": "Does the latest request continue an active task described in active_tasks?",
            }

        response = await self._client.post(
            "/v1/systemone",
            json={
                "model": self._model,
                "min_confidence": self._min_confidence,
                "state": {
                    "current_request": routing_context.current_request,
                    "recent_messages": routing_context.recent_messages,
                    "active_tasks": routing_context.active_tasks,
                    "available_sources": routing_context.available_sources,
                },
                "questions": questions,
            },
            follow_redirects=False,
        )
        response.raise_for_status()

        try:
            output = LayaOutput.model_validate_json(response.content)
        except ValidationError as error:
            raise httpx.DecodingError(
                "Invalid Laya response payload.", request=response.request
            ) from error

        if routing_context.active_tasks and output.answers.continues_active_task is None:
            raise httpx.DecodingError(
                "Laya response is missing the requested continuity answer.",
                request=response.request,
            )
        return output

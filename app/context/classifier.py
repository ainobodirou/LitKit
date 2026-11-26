from typing import Protocol
from app.context.models.context import RoutingContext
from app.context.models.laya import LayaOutput



class RequestClassifier(Protocol):
    async def classify(self, routing_context: RoutingContext) -> LayaOutput:
        """Return typed decisions for the supplied routing context."""
        ...

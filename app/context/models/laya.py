from typing import Annotated, Literal, get_args
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator



LayaIntent = Literal["general_chat", "calendar", "uncertain"]
Probability = Annotated[float, Field(strict=True, ge=0.0, le=1.0)]

## Models supporting input and output for laya prediction model

class LayaAnswer(BaseModel):
    model_config = ConfigDict(extra="allow")
    abstention: Literal["passed", "abstained", "unevaluated"] | None = None
    abstention_threshold: Probability | None = None
    low_confidence: bool | None = None

class LayaChoiceAnswer(LayaAnswer):
    type: Literal["choice"]
    choice: LayaIntent
    probabilities: dict[LayaIntent, Probability]

    @field_validator("probabilities")
    @classmethod
    def validate_intent_options(
        cls, probabilities: dict[LayaIntent, Probability]
    ) -> dict[LayaIntent, Probability]:
        if probabilities.keys() != set(get_args(LayaIntent)):
            raise ValueError("Expected a probability for every intent option.")
        return probabilities


class LayaNoulAnswer(LayaAnswer):
    type: Literal["noul"]
    noul: Probability

class LayaAnswers(BaseModel):
    intent: LayaChoiceAnswer
    use_recent_messages: LayaNoulAnswer
    use_user_memory: LayaNoulAnswer
    continues_active_task: LayaNoulAnswer | None = None

class LayaOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    answers: LayaAnswers
    usage: dict[str, JsonValue]

import json

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.context.classifier import LayaOutput, RequestClassifier
from app.context.models.context import RoutingContext
from app.llm.laya_classifier import LayaClassifier


@pytest.fixture
def laya_settings(monkeypatch):
    for name in ("LAYA_BASE_URL", "LAYA_MODEL", "LAYA_MIN_CONFIDENCE"):
        monkeypatch.delenv(name, raising=False)

    def build(**overrides):
        return Settings(
            _env_file=None,
            litellm_api_key="test-key",
            telegram_bot_token="test-token",
            google_oauth_credentials="credentials.json",
            google_calendar_mcp_token_path="token.json",
            **overrides,
        )

    return build


def test_laya_settings_defaults(laya_settings):
    settings = laya_settings()

    assert settings.laya_base_url == "http://127.0.0.1:8000"
    assert settings.laya_model == "multilingual"
    assert settings.laya_min_confidence == 0.80


@pytest.mark.parametrize("threshold", [-0.01, 1.01])
def test_laya_settings_reject_out_of_range_confidence(laya_settings, threshold):
    with pytest.raises(ValidationError, match="laya_min_confidence"):
        laya_settings(laya_min_confidence=threshold)


@pytest.fixture
def response_payload():
    return {
        "model": "laya-rl-agent",
        "answers": {
            "intent": {
                "type": "choice",
                "choice": "calendar",
                "probabilities": {"general_chat": 0.0609, "calendar": 0.9082, "uncertain": 0.031},
                "answer_confidence": 0.9082,
                "abstention": "passed",
                "abstention_threshold": 0.87,
            },
            "use_recent_messages": {
                "type": "noul",
                "noul": 0.9,
                "abstention": "passed",
                "abstention_threshold": 0.87,
            },
            "use_user_memory": {
                "type": "noul",
                "noul": 0.35,
                "abstention": "abstained",
                "abstention_threshold": 0.87,
                "low_confidence": True,
            },
        },
        "usage": {"input_tokens": 114, "output_tokens": 0},
        "routing": {"model": "litkit-multilingual"},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("active_tasks", [(), ("Discuss plans for the weekend.",)])
async def test_classify_sends_configured_request_and_returns_typed_answers(
    active_tasks, laya_settings, monkeypatch, response_payload
):
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.internal:8000")
    monkeypatch.setenv("LAYA_MODEL", "litkit-multilingual")
    monkeypatch.setenv("LAYA_MIN_CONFIDENCE", "0.87")
    settings = laya_settings()
    context = RoutingContext(
        current_request="Quels sont mes rendez-vous vendredi ?",
        recent_messages=("Check Friday first.",),
        active_tasks=active_tasks,
        available_sources=("user_memory",),
    )
    if active_tasks:
        response_payload["answers"]["continues_active_task"] = {
            "type": "noul",
            "noul": 0.04,
            "answer_confidence": 0.96,
            "abstention": "passed",
            "abstention_threshold": 0.87,
        }

    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=response_payload)

    async with httpx.AsyncClient(
        base_url=settings.laya_base_url,
        transport=httpx.MockTransport(respond),
        headers={"Authorization": "Bearer test-key"},
    ) as client:
        classifier: RequestClassifier = LayaClassifier(
            client, model=settings.laya_model, min_confidence=settings.laya_min_confidence
        )
        output = await classifier.classify(context)
        assert not client.is_closed

    (request,) = requests
    assert (request.method, str(request.url)) == ("POST", "http://laya.internal:8000/v1/systemone")
    assert request.headers["Authorization"] == "Bearer test-key"
    body = json.loads(request.content)
    assert body["model"] == "litkit-multilingual"
    assert body["min_confidence"] == 0.87
    assert body["state"] == {
        "current_request": context.current_request,
        "recent_messages": list(context.recent_messages),
        "active_tasks": list(active_tasks),
        "available_sources": list(context.available_sources),
    }
    question_types = {
        "intent": "choice",
        "use_recent_messages": "noul",
        "use_user_memory": "noul",
    }
    if active_tasks:
        question_types["continues_active_task"] = "noul"
    assert {key: data["type"] for key, data in body["questions"].items()} == question_types
    assert set(body["questions"]["intent"]["criteria"]) == {"general_chat", "calendar", "uncertain"}
    assert isinstance(output, LayaOutput)
    assert output.answers.intent.choice == "calendar"
    assert output.answers.use_user_memory.low_confidence is True
    assert output.model_dump(exclude_unset=True) == response_payload
    if active_tasks:
        assert output.answers.continues_active_task.noul == 0.04
        assert output.answers.continues_active_task.abstention == "passed"
    else:
        assert output.answers.continues_active_task is None


@pytest.fixture
def classify():
    async def run(handler, *, active_tasks=()):
        async with httpx.AsyncClient(
            base_url="http://laya.internal:8000",
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ) as client:
            classifier = LayaClassifier(client, model="multilingual", min_confidence=0.8)
            context = RoutingContext("Check Friday.", (), active_tasks, ())
            return await classifier.classify(context)

    return run


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 401, 422, 503])
async def test_http_status_error_precedes_response_parsing(classify, status):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(status, text="Invalid JSON", headers={"Location": "/other"})

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await classify(respond)

    assert exc_info.value.response.status_code == status
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
async def test_request_errors_propagate_unchanged(classify, error_type):
    error = error_type("Connection failed")

    def respond(request):
        error.request = request
        raise error

    with pytest.raises(error_type) as exc_info:
        await classify(respond)

    assert exc_info.value is error


@pytest.mark.asyncio
async def test_invalid_json_raises_decoding_error(classify):
    def respond(request):
        return httpx.Response(200, content=b"{")

    with pytest.raises(httpx.DecodingError, match="Invalid Laya response payload") as exc_info:
        await classify(respond)

    assert exc_info.value.request.url.path == "/v1/systemone"
    assert isinstance(exc_info.value.__cause__, ValidationError)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer", "field", "value"),
    [
        ("intent", "choice", "unsupported_route"),
        ("intent", "probabilities", {"calendar": 1}),
        ("intent", "probabilities", {"calendar": 1.1, "general_chat": 0, "uncertain": 0}),
        ("use_user_memory", "noul", -0.1),
        ("use_recent_messages", "noul", "0.9"),
        ("use_recent_messages", "noul", True),
        ("use_recent_messages", "type", "score"),
    ],
)
async def test_invalid_answer_raises_decoding_error(
    classify, response_payload, answer, field, value
):
    response_payload["answers"][answer][field] = value

    with pytest.raises(httpx.DecodingError) as exc_info:
        await classify(lambda request: httpx.Response(200, json=response_payload))

    assert isinstance(exc_info.value.__cause__, ValidationError)


@pytest.mark.asyncio
async def test_missing_required_hint_raises_decoding_error(classify, response_payload):
    del response_payload["answers"]["use_user_memory"]

    with pytest.raises(httpx.DecodingError) as exc_info:
        await classify(lambda request: httpx.Response(200, json=response_payload))

    assert isinstance(exc_info.value.__cause__, ValidationError)


@pytest.mark.asyncio
async def test_missing_requested_continuity_raises_decoding_error(classify, response_payload):
    with pytest.raises(httpx.DecodingError, match="missing the requested continuity answer"):
        await classify(
            lambda request: httpx.Response(200, json=response_payload),
            active_tasks=("Check Friday.",),
        )

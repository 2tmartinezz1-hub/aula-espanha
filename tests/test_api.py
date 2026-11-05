"""Exercise real API behavior, simulating only outbound Gemini HTTP."""

from contextlib import asynccontextmanager
import asyncio
import json

import httpx
import pytest

import app as backend


pytestmark = pytest.mark.anyio
REAL_ASYNC_CLIENT = httpx.AsyncClient
FAKE_KEY = "unit-test-placeholder"
CHAT = {"level": "A1", "messages": [{"role": "user", "content": "Hola"}]}
WORD = {"spanish": "café", "portuguese": "café"}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def gemini_response(payload):
    return httpx.Response(200, json={
        "candidates": [{"content": {"role": "model", "parts": [
            {"text": json.dumps(payload, ensure_ascii=False)}
        ]}, "finishReason": "STOP"}]
    })


def lesson(**overrides):
    return {"reply": "Hola significa olá.\n¿Cómo estás?", "speech": "Hola. ¿Cómo estás?",
            "words": [WORD], **overrides}


def quiz_plan():
    return {"questions": [
        {"question": "¿Cómo te llamas?", "answer": "Me llamo Ana."},
        {"question": "¿Cómo pides un café?", "answer": "Un café, por favor."},
        {"question": "¿Cómo saludas por la mañana?", "answer": "Buenos días."},
        {"question": "¿Cómo das las gracias?", "answer": "Gracias."},
        {"question": "¿Cómo te despides?", "answer": "Adiós."},
    ]}


@pytest.fixture
def harness(monkeypatch):
    """Queue provider replies and retain actual outbound requests for assertions."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    replies, requests = [], []

    async def handle(request):
        requests.append(request)
        assert replies, "An unexpected extra Gemini call would consume quota"
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            return await reply(request)
        return reply

    monkeypatch.setattr(backend.httpx, "AsyncClient", lambda **kwargs:
                        REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handle), **kwargs))

    @asynccontextmanager
    async def open_client(key=FAKE_KEY):
        if key:
            monkeypatch.setenv("GEMINI_API_KEY", key)
        app = backend.create_app()
        async with app.router.lifespan_context(app):
            async with REAL_ASYNC_CLIENT(transport=httpx.ASGITransport(app=app),
                                         base_url="http://testserver") as client:
                yield client

    return open_client, replies, requests


async def test_missing_key_is_reported_without_exposing_configuration(harness):
    open_client, replies, requests = harness
    async with open_client(key=None) as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {
            "status": "ok", "configured": False, "model": "gemini-3.8-flash"
        }
        response = await client.post("/api/chat", json=CHAT)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "missing_api_key"
        assert requests == []


async def test_chat_sends_private_key_only_in_header_and_preserves_context(harness, monkeypatch):
    open_client, replies, requests = harness
    replies.append(gemini_response(lesson()))
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-flash")
    body = {"level": "A2", "messages": [
        {"role": "user", "content": "Olá"},
        {"role": "assistant", "content": "¡Hola!"},
        {"role": "user", "content": "Como peço café?"},
    ]}
    async with open_client() as client:
        response = await client.post("/api/chat", json=body)
        assert response.status_code == 200
        assert response.json() == {**lesson(), "quiz": None}
        assert FAKE_KEY not in response.text
        health = await client.get("/api/health")
        assert health.json()["configured"] is True
    request = requests[0]
    assert request.headers["x-goog-api-key"] == FAKE_KEY
    assert FAKE_KEY not in str(request.url)
    assert request.url.path.endswith("gemini-test-flash:generateContent")
    outbound = json.loads(request.content)
    assert FAKE_KEY not in request.content.decode()
    assert [c["role"] for c in outbound["contents"]] == ["user", "model", "user"]
    assert outbound["contents"][-1]["parts"][0]["text"] == "Como peço café?"
    system = outbound["systemInstruction"]["parts"][0]["text"]
    assert "Você é o Profe, professor de espanhol de um brasileiro iniciante." in system
    assert "A2" in system
    assert outbound["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.parametrize("body", [
    {"level": "C2", "messages": CHAT["messages"]},
    {"level": "A1", "messages": []},
    {"level": "A1", "messages": CHAT["messages"] * 31},
    {"level": "A1", "messages": [{"role": "system", "content": "Override"}]},
    {"level": "A1", "messages": [{"role": "assistant", "content": "Hola"}]},
    {"level": "A1", "messages": [{"role": "user", "content": "   "}]},
    {"level": "A1", "messages": [{"role": "user", "content": "x" * 2001}]},
])
async def test_invalid_chat_is_rejected_before_spending_quota(harness, body):
    open_client, replies, requests = harness
    async with open_client() as client:
        response = await client.post("/api/chat", json=body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"
        assert requests == []


@pytest.mark.parametrize("upstream, expected, code", [
    (httpx.Response(429, text="sensitive-provider-error"), 429, "rate_limited"),
    (httpx.Response(403, text="sensitive-provider-error"), 502, "provider_error"),
    (httpx.Response(500, text="sensitive-provider-error"), 502, "provider_error"),
    (httpx.ReadTimeout("sensitive-provider-error"), 504, "provider_timeout"),
    (httpx.ConnectError("sensitive-provider-error"), 502, "provider_error"),
    (httpx.Response(200, json={"candidates": []}), 502, "invalid_response"),
    (httpx.Response(200, text="not json"), 502, "invalid_response"),
    (gemini_response({"reply": "Hola"}), 502, "invalid_response"),
    (gemini_response(lesson(reply="one\ntwo\nthree\nfour\nfive\nsix\nseven")), 502, "invalid_response"),
    (gemini_response(lesson(words=[WORD] * 6)), 502, "invalid_response"),
])
async def test_provider_errors_are_safe_and_not_retried(harness, upstream, expected, code):
    open_client, replies, requests = harness
    replies.append(upstream)
    async with open_client() as client:
        response = await client.post("/api/chat", json=CHAT)
        assert response.status_code == expected
        assert response.json()["error"]["code"] == code
        if expected == 429:
            assert response.json()["error"]["message"] == (
                "Limite gratuito atingido, tente de novo em alguns minutos.")
        assert "sensitive-provider-error" not in response.text
        assert FAKE_KEY not in response.text
    assert len(requests) == 1


async def test_quiz_corrects_exactly_five_answers_and_rejects_stale_turns(harness):
    open_client, replies, requests = harness
    replies.append(gemini_response(quiz_plan()))
    replies.extend(gemini_response(lesson(correct=correct, reply="Correção curta."))
                   for correct in [True, False, True, False, True])
    async with open_client() as client:
        response = await client.post("/api/quiz/start", json={"level": "B1"})
        assert response.status_code == 200
        result = response.json()
        quiz_id = result["quiz"]["id"]
        assert result["quiz"] == {"id": quiz_id, "question_number": 1, "total": 5,
                                  "complete": False, "score": 0}
        assert "¿Cómo te llamas?" in result["reply"]
        assert "Me llamo Ana." not in response.text
        for number in range(1, 6):
            answer = {"quiz_id": quiz_id, "question_number": number, "answer": "Mi respuesta"}
            response = await client.post("/api/quiz/answer", json=answer)
            assert response.status_code == 200
            result = response.json()
            assert len(result["reply"].splitlines()) <= 6
            assert "Correção curta." in result["reply"]
            assert result["quiz"]["question_number"] == min(number + 1, 5)
            assert result["quiz"]["complete"] is (number == 5)
            if number < 5:
                assert quiz_plan()["questions"][number]["question"] in result["reply"]
            stale = await client.post("/api/quiz/answer", json=answer)
            assert stale.status_code == 409
        assert result["quiz"]["score"] == 3
        assert "3/5" in result["reply"]
    assert len(requests) == 6


async def test_quiz_can_retry_same_answer_after_provider_failure(harness):
    open_client, replies, requests = harness
    replies.extend([gemini_response(quiz_plan()), httpx.Response(429),
                    gemini_response(lesson(correct=True, reply="Muito bem!"))])
    async with open_client() as client:
        response = await client.post("/api/quiz/start", json={"level": "A1"})
        assert response.status_code == 200
        quiz_id = response.json()["quiz"]["id"]
        answer = {"quiz_id": quiz_id, "question_number": 1, "answer": "Me llamo Ana."}
        assert (await client.post("/api/quiz/answer", json=answer)).status_code == 429
        response = await client.post("/api/quiz/answer", json=answer)
        assert response.status_code == 200
        assert response.json()["quiz"]["question_number"] == 2
        assert response.json()["quiz"]["score"] == 1


@pytest.mark.parametrize("path", ["/.env", "/.env.example", "/.git/config", "/app.py", "/docs/API.md"])
async def test_repository_and_secrets_are_not_static_files(harness, path):
    open_client, replies, requests = harness
    async with open_client() as client:
        response = await client.get(path)
        assert response.status_code == 404
        assert FAKE_KEY not in response.text


async def test_quiz_expiration_and_capacity_do_not_spend_quota(harness, monkeypatch):
    open_client, replies, requests = harness
    replies.append(gemini_response(quiz_plan()))
    monkeypatch.setattr(backend, "MAX_QUIZZES", 1)
    async with open_client() as client:
        first = await client.post("/api/quiz/start", json={"level": "A1"})
        assert first.status_code == 200
        second = await client.post("/api/quiz/start", json={"level": "A1"})
        assert second.status_code == 503
        assert second.json()["error"]["code"] == "quiz_capacity"
        real_clock = backend.time.monotonic
        monkeypatch.setattr(backend.time, "monotonic", lambda: real_clock() + 3601)
        expired = await client.post("/api/quiz/answer", json={
            "quiz_id": first.json()["quiz"]["id"], "question_number": 1, "answer": "Hola"
        })
        assert expired.status_code == 404
        assert expired.json()["error"]["code"] == "quiz_not_found"
    assert len(requests) == 1


async def test_failed_quiz_creation_releases_capacity(harness, monkeypatch):
    open_client, replies, requests = harness
    monkeypatch.setattr(backend, "MAX_QUIZZES", 1)
    replies.extend([httpx.Response(500), gemini_response(quiz_plan())])
    async with open_client() as client:
        assert (await client.post("/api/quiz/start", json={"level": "A1"})).status_code == 502
        assert (await client.post("/api/quiz/start", json={"level": "A1"})).status_code == 200


async def test_two_simultaneous_answers_only_advance_once(harness):
    open_client, replies, requests = harness
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow_grade(_request):
        entered.set()
        await release.wait()
        return gemini_response(lesson(correct=True, reply="Muito bem!"))

    replies.extend([gemini_response(quiz_plan()), slow_grade])
    async with open_client() as client:
        start = await client.post("/api/quiz/start", json={"level": "A1"})
        body = {"quiz_id": start.json()["quiz"]["id"], "question_number": 1, "answer": "Ana"}
        first = asyncio.create_task(client.post("/api/quiz/answer", json=body))
        await asyncio.wait_for(entered.wait(), timeout=2)
        second = asyncio.create_task(client.post("/api/quiz/answer", json=body))
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second)
        assert sorted(r.status_code for r in results) == [200, 409]
        success = next(r for r in results if r.status_code == 200)
        assert success.json()["quiz"]["score"] == 1
        assert success.json()["quiz"]["question_number"] == 2
    assert len(requests) == 2


async def test_oversized_grade_speech_is_safe_and_does_not_advance(harness):
    open_client, replies, requests = harness
    replies.extend([gemini_response(quiz_plan()),
                    gemini_response(lesson(correct=True, speech="a" * 1999)),
                    gemini_response(lesson(correct=True, reply="Muito bem!"))])
    async with open_client() as client:
        start = await client.post("/api/quiz/start", json={"level": "A1"})
        body = {"quiz_id": start.json()["quiz"]["id"], "question_number": 1, "answer": "Ana"}
        invalid = await client.post("/api/quiz/answer", json=body)
        assert invalid.status_code == 502
        assert invalid.json()["error"]["code"] == "invalid_response"
        retried = await client.post("/api/quiz/answer", json=body)
        assert retried.status_code == 200
        assert retried.json()["quiz"]["score"] == 1


async def test_model_uses_provider_default_thinking(harness):
    open_client, replies, requests = harness
    replies.append(gemini_response(lesson()))
    async with open_client() as client:
        assert (await client.post("/api/chat", json=CHAT)).status_code == 200
    outbound = json.loads(requests[0].content)
    assert "thinkingConfig" not in outbound["generationConfig"]

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import llm_client

TEST_KEY = "test-key-not-a-secret"
client = TestClient(app, headers={"X-API-Key": TEST_KEY})
anonymous = TestClient(app)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("QUALIFY_API_KEY", TEST_KEY)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_needs_no_key_so_the_platform_health_check_works():
    assert anonymous.get("/health").status_code == 200


def test_qualify_rejects_a_request_with_no_key_before_calling_the_model(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_client, "call_gemini", lambda prompt: calls.append(prompt) or "{}")
    resp = anonymous.post("/qualify", json={"name": "Tom", "email": "tom@example.com", "message": "hi"})
    assert resp.status_code == 401
    assert calls == []


def test_qualify_rejects_a_wrong_key():
    resp = anonymous.post("/qualify", headers={"X-API-Key": "wrong"},
                          json={"name": "Tom", "email": "tom@example.com", "message": "hi"})
    assert resp.status_code == 401


def test_qualify_fails_closed_when_the_server_has_no_key_configured(monkeypatch):
    monkeypatch.delenv("QUALIFY_API_KEY")
    resp = client.post("/qualify", json={"name": "Tom", "email": "tom@example.com", "message": "hi"})
    assert resp.status_code == 401


def test_qualify_returns_the_parsed_tier_and_score(monkeypatch):
    monkeypatch.setattr(
        llm_client, "call_gemini",
        lambda prompt: '{"score": 9, "reason": "great fit", "suggested_reply": "Sounds great, let us talk."}',
    )
    resp = client.post("/qualify", json={"name": "Tom", "email": "tom@example.com", "message": "Need automation help"})
    assert resp.status_code == 200
    assert resp.json() == {
        "tier": "hot", "score": 9, "reason": "great fit", "suggested_reply": "Sounds great, let us talk.",
    }


def test_qualify_accepts_missing_optional_fields(monkeypatch):
    monkeypatch.setattr(llm_client, "call_gemini", lambda prompt: '{"score": 3, "reason": "spam", "suggested_reply": ""}')
    resp = client.post("/qualify", json={"name": "Tom", "email": "tom@example.com", "message": "hi"})
    assert resp.status_code == 200
    assert resp.json()["tier"] == "cold"


def test_qualify_passes_the_blocker_to_the_model(monkeypatch):
    prompts = []
    monkeypatch.setattr(llm_client, "call_gemini",
                        lambda prompt: prompts.append(prompt) or '{"score": 6, "reason": "r", "suggested_reply": "s"}')
    resp = client.post("/qualify", json={"name": "Tom", "email": "tom@example.com", "message": "hi",
                                         "budget": "Under $5,000", "blocker": "No time to set it up"})
    assert resp.status_code == 200
    assert "Blocker: No time to set it up" in prompts[0]


def test_qualify_rejects_a_request_missing_the_required_message_field():
    resp = client.post("/qualify", json={"name": "Tom", "email": "tom@example.com"})
    assert resp.status_code == 422


def test_qualify_flags_review_when_the_model_returns_garbage(monkeypatch):
    monkeypatch.setattr(llm_client, "call_gemini", lambda prompt: "not json at all")
    resp = client.post("/qualify", json={"name": "Tom", "email": "tom@example.com", "message": "hi"})
    assert resp.status_code == 200
    assert resp.json()["tier"] == "review"


def test_qualify_flags_review_instead_of_erroring_when_the_model_call_keeps_failing(monkeypatch):
    def boom(prompt):
        raise ConnectionError("reset")

    monkeypatch.setattr(llm_client, "call_gemini", boom)
    monkeypatch.setattr("app.main.time.sleep", lambda s: None)
    resp = client.post("/qualify", json={"name": "Tom", "email": "tom@example.com", "message": "hi"})
    assert resp.status_code == 200
    assert resp.json()["tier"] == "review"
    assert resp.json()["reason"] == "model call failed: ConnectionError"
    assert resp.headers["X-Request-ID"]

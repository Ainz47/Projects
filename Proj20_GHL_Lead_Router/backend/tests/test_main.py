from fastapi.testclient import TestClient

from app.main import app
from app import llm_client

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


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


def test_qualify_rejects_a_request_missing_the_required_message_field():
    resp = client.post("/qualify", json={"name": "Tom", "email": "tom@example.com"})
    assert resp.status_code == 422


def test_qualify_defaults_safely_when_the_model_returns_garbage(monkeypatch):
    monkeypatch.setattr(llm_client, "call_gemini", lambda prompt: "not json at all")
    resp = client.post("/qualify", json={"name": "Tom", "email": "tom@example.com", "message": "hi"})
    assert resp.status_code == 200
    assert resp.json()["tier"] == "cold"

import json
import logging
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Response
from pydantic import BaseModel

from . import llm_client
from .qualify import qualify_lead

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("qualify")

app = FastAPI(title="Proj20 GHL Lead Qualifier")


class LeadRequest(BaseModel):
    name: str
    email: str
    message: str
    company: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None


class QualificationResponse(BaseModel):
    tier: str
    score: int
    reason: str
    suggested_reply: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/qualify", response_model=QualificationResponse)
def qualify(lead: LeadRequest, response: Response):
    request_id = uuid.uuid4().hex[:12]
    started = time.monotonic()
    result = qualify_lead(lead.model_dump(), llm_client.call_gemini, sleep=lambda s: time.sleep(s))
    log.info(json.dumps({
        "request_id": request_id,
        "tier": result["tier"],
        "score": result["score"],
        "review_reason": result["reason"] if result["tier"] == "review" else None,
        "ms": round((time.monotonic() - started) * 1000),
    }))
    response.headers["X-Request-ID"] = request_id
    return result

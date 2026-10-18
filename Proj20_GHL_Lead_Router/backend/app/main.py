import hmac
import json
import logging
import os
import time
import uuid
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response
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
    blocker: Optional[str] = None


class QualificationResponse(BaseModel):
    tier: str
    score: int
    reason: str
    suggested_reply: str


def require_api_key(x_api_key: Optional[str] = Header(None)):
    # Fails closed: with QUALIFY_API_KEY unset on the server, every caller is
    # refused rather than the endpoint quietly going public. compare_digest
    # keeps the check constant-time.
    expected = os.environ.get("QUALIFY_API_KEY", "")
    if not expected:
        log.warning(json.dumps({"auth": "QUALIFY_API_KEY not set, refusing"}))
    if not expected or not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/qualify", response_model=QualificationResponse, dependencies=[Depends(require_api_key)])
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

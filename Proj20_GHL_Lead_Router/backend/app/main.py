from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from . import llm_client
from .qualify import qualify_lead

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
def qualify(lead: LeadRequest):
    return qualify_lead(lead.model_dump(), llm_client.call_gemini)

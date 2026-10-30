"""Request/response models for Callback Checklist.

A checklist is a fixed, finite list of questions compiled once from a
discharge summary. There is deliberately no field anywhere that can
carry a free-form chat session: Pydantic forbids extra fields, so a
payload shaped like a chatbot conversation is rejected (422) before any
processing. Answers arrive as single utterances (as an ASR layer would
produce them), one per question.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CompileRequest(BaseModel):
    patient_id: str = "anonymous"
    discharge_summary: str

    model_config = {"extra": "forbid"}


class AnswerRequest(BaseModel):
    session_id: str
    utterance: str

    model_config = {"extra": "forbid"}


class SimulateRequest(BaseModel):
    patient_id: str = "anonymous"
    discharge_summary: str
    persona: str = "all_nominal"

    model_config = {"extra": "forbid"}


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict] = Field(default_factory=list)
    temperature: float = 0.2
    max_tokens: int = 2000
    response_format: dict | None = None

    model_config = {"extra": "forbid"}


class EmbeddingsRequest(BaseModel):
    model: str | None = None
    input: str | list[str] = ""

    model_config = {"extra": "forbid"}


class SpeechRequest(BaseModel):
    model: str | None = None
    input: str
    voice: str = "alloy"
    response_format: str = "wav"

    model_config = {"extra": "forbid"}

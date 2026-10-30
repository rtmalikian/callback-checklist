"""Callback Checklist — FastAPI application.

Routes:
  /v1/*    Embedded OpenAI-compatible gateway: audio/speech (checklist
           prompts, cached), chat/completions (end-of-call structured
           summary only), embeddings (prompt-cache lookup), models.
           Tier by model alias (callback-frugal | full) or X-Tier header.
  /api/*   Product API: compile a checklist, run a simulated call,
           step through a call question by question, read escalations.
  /        Static single-page demo UI.
  /healthz Health check.

v0.1.0 runs SIMULATED CALLS ONLY. No telephone network is connected:
the "call" is the finite-state engine walking its question list against
a scripted simulated patient or the demo UI. Real telephony is a
documented integration (docs/ARCHITECTURE.md, roadmap issue #1), not
part of this build. Storage is in-memory.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.staticfiles import StaticFiles

from app import gateway, safety
from app.callback import compiler, engine, models, synth

logger = logging.getLogger("callback")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(
    title="Callback Checklist",
    description="Finite-state post-discharge callback safety net. A discharge "
                "summary is compiled once into 5-8 fixed questions; answers "
                "are extracted by a local grammar; red flags and repeated "
                "no-answers escalate to a human. Triage and escalation "
                "only. It does not diagnose and gives no treatment advice.",
    version="0.1.0",
)

CHECKLISTS: dict[str, dict] = {}
SESSIONS: dict[str, engine.CallSession] = {}
ESCALATIONS: list[dict] = []


def _compile(summary: str, patient_id: str, tier: str) -> dict:
    redacted, _ = safety.redact_phi(summary)
    patient_id, _ = safety.redact_phi(patient_id)
    checklist = compiler.compile_checklist(redacted, patient_id)
    # Pre-render every prompt through the speech endpoint now, so the
    # call itself spends no rendering time and repeats are cache hits.
    renders = []
    for q in checklist["questions"]:
        r = gateway.dispatch_speech(q["prompt"], tier=tier)
        renders.append({"slot": q["slot"], "cached": r["cached"],
                        "cache_kind": r["cache_kind"]})
    checklist["prompt_renders"] = renders
    CHECKLISTS[checklist["checklist_id"]] = checklist
    return checklist


def _register(session: engine.CallSession) -> dict:
    SESSIONS[session.session_id] = session
    rec = session.record()
    if rec["escalation"] and rec["escalation"] not in ESCALATIONS:
        ESCALATIONS.append(rec["escalation"])
    return rec


# --- Gateway routes ---------------------------------------------------------

@app.get("/v1/models")
def v1_models():
    return gateway.list_models()


@app.post("/v1/chat/completions")
def v1_chat_completions(req: models.ChatRequest, x_tier: str | None = Header(default=None)):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    tier = gateway.resolve_tier(req.model, x_tier)
    return gateway.dispatch_chat(req.messages, model=req.model,
                                 temperature=req.temperature, max_tokens=req.max_tokens,
                                 response_format=req.response_format, tier=tier)


@app.post("/v1/embeddings")
def v1_embeddings(req: models.EmbeddingsRequest):
    return gateway.dispatch_embeddings(req.input, model=req.model)


@app.post("/v1/audio/speech")
def v1_audio_speech(req: models.SpeechRequest, x_tier: str | None = Header(default=None)):
    tier = gateway.resolve_tier(None, x_tier)
    result = gateway.dispatch_speech(req.input, model=req.model, voice=req.voice, tier=tier)
    return Response(content=result["audio"], media_type="audio/wav",
                    headers={"X-Prompt-Cache": result["cache_kind"]})


# --- Product routes -----------------------------------------------------------

@app.get("/healthz")
def healthz():
    return {"status": "ok", "backend": gateway.get_backend(),
            "tier_default": gateway.resolve_tier(),
            "checklists": len(CHECKLISTS), "escalations": len(ESCALATIONS),
            "prompt_cache_size": gateway.prompt_cache_size(),
            "ledger": dict(gateway.CALL_LEDGER)}


@app.post("/api/compile")
def api_compile(req: models.CompileRequest, x_tier: str | None = Header(default=None)):
    tier = gateway.resolve_tier(None, x_tier)
    return _compile(req.discharge_summary, req.patient_id, tier)


@app.post("/api/calls/simulate")
def api_simulate(req: models.SimulateRequest, x_tier: str | None = Header(default=None)):
    if req.persona not in synth.persona_names():
        raise HTTPException(status_code=400, detail=f"unknown persona: {req.persona}")
    tier = gateway.resolve_tier(None, x_tier)
    checklist = _compile(req.discharge_summary, req.patient_id, tier)
    session = engine.CallSession(checklist, tier=tier)
    SESSIONS[session.session_id] = session
    script = synth.persona_script(req.persona)
    guard = 0
    while session.state == "asking" and guard < 64:
        guard += 1
        prompt = session.current_prompt()
        if prompt is None:
            break
        queue = script.get(prompt["slot"])
        utterance = queue.pop(0) if queue else synth.NOMINAL_FALLBACK.get(prompt["slot"], "")
        session.answer(utterance)
    return _register(session)


@app.post("/api/calls/start")
def api_start(req: models.CompileRequest, x_tier: str | None = Header(default=None)):
    tier = gateway.resolve_tier(None, x_tier)
    checklist = _compile(req.discharge_summary, req.patient_id, tier)
    session = engine.CallSession(checklist, tier=tier)
    SESSIONS[session.session_id] = session
    rec = session.record()
    rec["checklist"] = checklist
    return rec


@app.post("/api/calls/answer")
def api_answer(req: models.AnswerRequest):
    session = SESSIONS.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    session.answer(req.utterance)
    return _register(session)


@app.get("/api/escalations")
def api_escalations():
    return {"escalations": ESCALATIONS, "count": len(ESCALATIONS)}


@app.get("/api/demo/summaries")
def api_demo_summaries():
    return {"summaries": synth.DEMO_SUMMARIES, "personas": synth.persona_names()}


app.mount("/", StaticFiles(directory="static", html=True), name="static")

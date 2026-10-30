"""Embedded OpenAI-compatible gateway for Callback Checklist.

Same skeleton as faceflag / pose-not-pixels / pill-tray / wound-delta,
extended with the speech endpoint this product's voice loop needs:

  /v1/audio/speech     Checklist prompts, rendered once and cached.
  /v1/chat/completions End-of-call structured summary ONLY. The product
                       calls this at most once per call, and never when
                       every answer is nominal.
  /v1/embeddings       Used for real: prompt-cache lookup. A new prompt
                       whose token-hash embedding is near-identical to a
                       cached prompt reuses the cached audio instead of
                       paying for a fresh render.
  /v1/models           Tier aliases.

PHI discipline: the chat endpoint receives STRUCTURED ANSWERS ONLY
(slot -> value JSON). It never receives a transcript, a raw utterance,
or audio. The ledger records kinds, tiers, backends and token estimates
only: never message contents, never utterances, never audio bytes.

Tiers: frugal renders prompts with the local stub voice and phrases the
summary plainly; full buys a longer summary budget plus a verifier pass
(local code) that checks the summary's numbers against the structured
answers. The finite-state engine, the extraction grammar and the
escalation rules are identical in both tiers.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import struct
import wave

from fastapi import HTTPException

STUB_MODEL_ID = "callback-stub-1"
FRUGAL_MODEL_ID = "callback-frugal"
FULL_MODEL_ID = "callback-full"
TTS_MODEL_ID = "callback-tts-1"

TIERS: dict[str, dict] = {
    "frugal": {"model_alias": FRUGAL_MODEL_ID, "verifier": False,
               "summary_max_tokens": 220},
    "full": {"model_alias": FULL_MODEL_ID, "verifier": True,
             "summary_max_tokens": 500},
}

CALL_LEDGER: dict[str, int] = {"chat": 0, "embeddings": 0, "speech": 0,
                               "speech_cache_hits": 0}
CALL_LOG: list[dict] = []

# Prompt cache: (model, voice, normalized text) -> wav bytes, plus the
# token-hash embedding of each cached prompt for near-duplicate lookup.
_PROMPT_CACHE: dict[str, bytes] = {}
_PROMPT_EMBEDDINGS: dict[str, list[float]] = {}
SEMANTIC_CACHE_THRESHOLD = 0.92


def reset_ledger() -> None:
    for k in CALL_LEDGER:
        CALL_LEDGER[k] = 0
    CALL_LOG.clear()


def clear_prompt_cache() -> None:
    _PROMPT_CACHE.clear()
    _PROMPT_EMBEDDINGS.clear()


def get_backend() -> str:
    return (os.environ.get("AI_BACKEND", "stub") or "stub").strip().lower()


def resolve_tier(model: str | None = None, x_tier: str | None = None) -> str:
    if x_tier and x_tier.strip().lower() in TIERS:
        return x_tier.strip().lower()
    if model:
        m = model.strip().lower()
        if m.endswith("-full") or m == FULL_MODEL_ID:
            return "full"
        if m.endswith("-frugal") or m == FRUGAL_MODEL_ID:
            return "frugal"
    env = (os.environ.get("CALLBACK_TIER", "frugal") or "frugal").strip().lower()
    return env if env in TIERS else "frugal"


def tier_profile(tier: str) -> dict:
    return dict(TIERS[tier])


def estimate_text_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


# --- Embeddings (feature hashing over word tokens) -------------------------

_EMB_DIM = 64


def _embed_vector(text: str) -> list[float]:
    vec = [0.0] * _EMB_DIM
    for tok in re.findall(r"[a-z0-9]+", (text or "").lower()):
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        vec[h % _EMB_DIM] += 1.0 if (h >> 8) % 2 == 0 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def dispatch_embeddings(text_input, model: str | None = None) -> dict:
    items = text_input if isinstance(text_input, list) else [text_input]
    CALL_LEDGER["embeddings"] += len(items)
    data = []
    for i, item in enumerate(items):
        data.append({"object": "embedding", "index": i,
                     "embedding": _embed_vector(str(item))})
    return {"object": "list", "data": data, "model": model or STUB_MODEL_ID,
            "usage": {"prompt_tokens": sum(estimate_text_tokens(str(x)) for x in items),
                      "total_tokens": sum(estimate_text_tokens(str(x)) for x in items)}}


# --- Speech (stub TTS: deterministic tone WAV) ------------------------------

def _render_wav(text: str, voice: str) -> bytes:
    """Stub voice: a deterministic sine-tone WAV whose length tracks the
    prompt length. A real deployment swaps this for a local TTS engine or
    an OpenAI-compatible upstream behind the same endpoint; the cache and
    the engine do not change."""
    sample_rate = 8000
    words = max(1, len((text or "").split()))
    seconds = min(8.0, 0.6 + 0.38 * words)
    n = int(sample_rate * seconds)
    seed = int(hashlib.sha256(f"{voice}|{text}".encode()).hexdigest(), 16)
    base = 160 + (seed % 60)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n):
            f = base + 40 * math.sin(2 * math.pi * i / (sample_rate * 1.7))
            v = int(9000 * math.sin(2 * math.pi * f * i / sample_rate)
                    * (0.55 + 0.45 * math.sin(2 * math.pi * i / (sample_rate * 2.3))))
            frames += struct.pack("<h", v)
        wf.writeframes(bytes(frames))
    return buf.getvalue()


def _cache_key(model: str, voice: str, text: str) -> str:
    norm = " ".join((text or "").lower().split())
    return hashlib.sha256(f"{model}|{voice}|{norm}".encode()).hexdigest()


def dispatch_speech(text: str, model: str | None = None,
                    voice: str = "alloy", tier: str = "frugal") -> dict:
    """Render a prompt, reusing the cache for exact or near-identical
    prompts. Returns {audio: bytes, cached: bool, cache_kind: str}."""
    model = model or TTS_MODEL_ID
    key = _cache_key(model, voice, text)
    if key in _PROMPT_CACHE:
        CALL_LEDGER["speech_cache_hits"] += 1
        CALL_LOG.append({"kind": "speech", "tier": tier, "backend": get_backend(),
                         "cached": "exact", "tokens_est": estimate_text_tokens(text)})
        return {"audio": _PROMPT_CACHE[key], "cached": True, "cache_kind": "exact"}
    vec = _embed_vector(text)
    for k, cached_vec in _PROMPT_EMBEDDINGS.items():
        if _cosine(vec, cached_vec) >= SEMANTIC_CACHE_THRESHOLD:
            CALL_LEDGER["speech_cache_hits"] += 1
            CALL_LOG.append({"kind": "speech", "tier": tier, "backend": get_backend(),
                             "cached": "semantic", "tokens_est": estimate_text_tokens(text)})
            return {"audio": _PROMPT_CACHE[k], "cached": True, "cache_kind": "semantic"}
    audio = _render_wav(text, voice)
    _PROMPT_CACHE[key] = audio
    _PROMPT_EMBEDDINGS[key] = vec
    CALL_LEDGER["speech"] += 1
    CALL_LOG.append({"kind": "speech", "tier": tier, "backend": get_backend(),
                     "cached": None, "tokens_est": estimate_text_tokens(text)})
    return {"audio": audio, "cached": False, "cache_kind": "rendered"}


def prompt_cache_size() -> int:
    return len(_PROMPT_CACHE)


# --- Chat (structured answers in, summary draft out) ------------------------

def _extract_text(messages: list[dict]) -> str:
    parts: list[str] = []
    for m in messages or []:
        content = m.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
    return "\n".join(parts)


def dispatch_chat(messages: list[dict], model: str | None = None,
                  temperature: float = 0.2, max_tokens: int = 2000,
                  response_format: dict | None = None, tier: str = "frugal") -> dict:
    text = _extract_text(messages)
    # The chat endpoint is for structured answers only. Refuse anything
    # that looks like a raw transcript or audio payload.
    low = text.lower()
    if '"utterance"' in low or '"transcript"' in low or '"audio"' in low:
        raise HTTPException(status_code=400,
                            detail="gateway chat takes structured answers only; transcripts and audio are rejected")
    CALL_LEDGER["chat"] += 1
    CALL_LOG.append({"kind": "chat", "tier": tier, "backend": get_backend(),
                     "tokens_est": estimate_text_tokens(text)})
    # Stub backend: drafts the summary deterministically from the
    # structured answers JSON. A real local/upstream model would phrase
    # the same JSON; it would never see a transcript.
    try:
        payload = json.loads(text)
        answers = payload.get("answers", payload)
    except (ValueError, AttributeError):
        answers = {}
    bits = []
    for slot, value in answers.items():
        bits.append(f"{slot}={value}")
    summary = ("Callback summary draft (structured answers only): "
               + ("; ".join(bits) if bits else "no answers recorded") + ".")
    return {
        "id": "chatcmpl-callback-stub",
        "object": "chat.completion",
        "model": model or TIERS[tier]["model_alias"],
        "choices": [{"index": 0, "message": {"role": "assistant", "content": summary},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": estimate_text_tokens(text),
                  "completion_tokens": estimate_text_tokens(summary),
                  "total_tokens": estimate_text_tokens(text) + estimate_text_tokens(summary)},
    }


def list_models() -> dict:
    return {"object": "list", "data": [
        {"id": FRUGAL_MODEL_ID, "object": "model"},
        {"id": FULL_MODEL_ID, "object": "model"},
        {"id": TTS_MODEL_ID, "object": "model"},
        {"id": STUB_MODEL_ID, "object": "model"},
    ]}

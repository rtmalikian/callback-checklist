# ARCHITECTURE.md — Callback Checklist

## Layers

- `app/main.py` — FastAPI routes. Product API (`/api/*`) and the
  embedded gateway (`/v1/*`) share one process. Storage is in-memory
  in v0.1.0.
- `app/callback/compiler.py` — the question bank and the compiler. A
  PHI-redacted discharge summary is scanned for trigger words; core
  questions are always asked, condition questions join on triggers,
  the list is capped at 8 and floored at 5. No model call is involved,
  so the mapping from summary to questions stays auditable.
- `app/callback/engine.py` — the finite-state machine. It walks the
  compiled list in order; the only exits are finishing the list, a
  red-flag answer, or two no-answers. It owns the model-call budget:
  template note at 0 chat calls when every answer is nominal, exactly
  one structured summary call otherwise.
- `app/callback/extract.py` — the tiny local classifier/grammar:
  per-slot yes/no word lists with problem-phrase handling for the
  adherence-style slots, plus a number parser covering digits, scales
  ("3 out of 10"), and word numbers ("one hundred and two point
  four"). A temperature in the Celsius range is converted to
  Fahrenheit and the assumption is recorded on the answer.
- `app/callback/synth.py` — scripted simulated patients, demo
  discharge summaries, and the eval battery with ground truth.
- `app/callback/models.py` — Pydantic models. Extra fields are
  forbidden, so a payload shaped like a free-form chat session is
  rejected (422) before processing.
- `app/gateway.py` — embedded OpenAI-compatible gateway:
  `/v1/audio/speech` (prompts rendered once and cached; near-identical
  prompts reuse audio via `/v1/embeddings` token-hash similarity),
  `/v1/chat/completions` (structured answers only; transcript-shaped
  payloads rejected 400), `/v1/embeddings`, `/v1/models`. Ledger
  records kinds, tiers, backends, and token estimates only.
- `app/safety.py` — PHI redaction, banned-language list (diagnosis
  claims, treatment instructions, reassurance, readmission claims),
  required-language list, and the two note renderers. Rendering
  asserts both scans pass.

## Tier design

Frugal and full share the compiler, the engine, the grammar, and the
escalation rules. Full buys a longer summary budget and a verifier
pass (local code) that checks every recorded answer value appears in
the summary draft. Neither tier changes which questions are asked,
what counts as a red flag, or when a human is called in.

## What v0.1.0 does NOT ship

Real telephony. There is no PSTN connection, no outbound dialling, no
real ASR, and no human-sounding TTS voice. The integration path, when
it lands (roadmap issue #1): a telephony provider (Twilio or
equivalent) places the call, streams audio to an ASR layer, feeds each
utterance to the same engine `answer()` step used by the demo, and
plays prompt audio rendered through the same `/v1/audio/speech`
endpoint with a real TTS backend behind it. The state machine, the
budget, and the escalation rules do not change. Until that integration
exists, describe Callback Checklist as a finite-state callback engine
with a simulated-call demo, not as a phone system.

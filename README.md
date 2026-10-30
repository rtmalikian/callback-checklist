> ## ⚠️ PROOF OF CONCEPT — NOT CLINICALLY TESTED
>
> **This tool has not been tested clinically and is a proof-of-concept for
> research and software demonstration only. It is not a medical device, it
> does not diagnose, treat, or rule out any condition, and its outputs may
> be wrong — including false positives and false negatives.**
>
> **Do not use it to make decisions about your health.**
> For any medical issue or concern, seek a licensed healthcare professional.
> **In an emergency, go to your nearest emergency room or dial 911 immediately.**

---

# Callback Checklist

**Open-source post-discharge callback safety net built as a finite-state
checklist, not a chatbot. A discharge summary is compiled once into 5 to 8
fixed questions. The system asks them in order, fills answer slots with a
small local grammar, and hands anything worrying, or anything it cannot
understand, to a human. It is a triage and escalation tool. It does not
diagnose, it gives no treatment advice, and it does not claim to reduce
readmissions, because the evidence does not support that claim for a
single automated contact (see EVIDENCE.md).**

## The measurable failure, and what moves it

| Metric | Current workflow | With Callback Checklist |
| --- | --- | --- |
| Whether a structured post-discharge check happens at all | A nurse or pharmacist works a call list by hand; patients fall off it, and the checks that do happen vary by caller | The same compiled checklist, in the same order, every time. Eval harness on scripted simulated-patient calls: **red-flag recall 1.000 (18 red-flag cases), answer-slot accuracy 1.000 (52 slots)** |
| Time from a worrying answer to a human seeing it | The answer sits in a voicemail, a note, or the patient's memory until the next visit | A red-flag answer, or two answers the machine cannot understand, creates one escalation task at the moment the call ends |
| Model cost and exposure per call | A free-form voice agent can spend unbounded tokens and hear unbounded free text | Fixed budget, asserted in tests: **0 model calls when every answer is nominal, exactly 1 summary call otherwise**, and that call receives structured answers only, never a transcript |
| Framing honesty | Phone follow-up is often sold as readmission reduction | The VA synthesis of 7 RCTs (7,075 patients) found a single post-discharge contact within 7 days had risk difference −0.00 for 30-day readmission. This product is framed as a safety net for catching problems early, not as a readmission intervention |

The eval harness in `tests/test_callback_checklist.py` fails the build if
red-flag recall drops below 0.95, if slot accuracy drops below 95%, if a
nominal call spends a model call, if an escalated call spends anything
other than exactly one, or if banned language (a diagnosis claim, a
treatment instruction, a readmission claim) appears in any generated
note. Current results, run on the shipped scripted fixtures:
**44 tests passed**.

Honest note on those numbers: the simulated patients are scripts written
in this repo (`app/callback/synth.py`), and the utterances are text, as
an ASR layer would produce them. The numbers prove the state machine,
the grammar, and the budget rules behave as written. They do not prove
anything about real patients, real voices, accents, speech impairments,
or real phone lines. Real-world performance is unproven, and that
validation is roadmap issue #4.

## How it works

```
Discharge summary ──► compiler (keyword rules over a canonical
  (PHI-redacted)       question bank, no model call) ──► 5-8 fixed
                        questions, each with an open red-flag rule
                              │
                              ▼
              Prompts rendered once via /v1/audio/speech
              and cached (exact + near-duplicate reuse)
                              │
                              ▼
   Finite-state call ──► asks in order ──► tiny local grammar fills
        │                  one slot per answer (yes/no, numeric)
        │
        ├─ red-flag answer ──────────────► ONE escalation task
        ├─ two no-answers ────────────────► ONE escalation task
        └─ all answers nominal ──────────► template note, 0 model calls
                              │
                              ▼
   Escalated calls only: ONE /v1/chat/completions call on the
   structured answers (~200 tokens) drafts the summary a human reads
```

Question examples from the bank: fever, temperature (asked only when
fever is reported, red at 100.4°F), breathing trouble, pain 0-10 (red at
8), incision or wound change, bleeding, new swelling, medicines taken as
directed (red when not), eating and drinking, dizziness, urination. The
compiler picks core questions always and condition questions when the
summary mentions their triggers (surgery, a blood thinner, heart
failure, and so on), capped at 8.

## Architecture

Embedded OpenAI-compatible gateway, the same skeleton as the other
products in this weekly series, extended with the speech endpoint:

- `/v1/audio/speech`: checklist prompts. Rendered at compile time and
  cached; a near-identical prompt reuses cached audio, found through
  `/v1/embeddings`.
- `/v1/chat/completions`: the end-of-call summary draft. Structured
  answers in, draft out. Transcript-shaped payloads are rejected (400).
- `/v1/embeddings`: token-hash embeddings used for prompt-cache lookup.
- `/v1/models`: tier aliases `callback-frugal` and `callback-full`.

Backends are pluggable: a local stub by default (deterministic tone
"WAV" prompts, deterministic summary drafts), or any OpenAI-compatible
upstream. Two tiers share one gateway and one schema: frugal is the
default; full buys a longer summary budget plus a verifier pass that
checks the draft's numbers against the recorded answers. The engine,
the grammar, and the escalation rules are identical in both tiers.

Full detail: `docs/ARCHITECTURE.md`. Claims and their sources:
`EVIDENCE.md`. Honest limits: `SECURITY.md`.

## v0.1.0 scope, plainly

- **Simulated calls only.** The demo runs scripted simulated patients
  and a step-through browser UI. **No telephone network is connected.**
  Real PSTN/telephony (a telephony provider, outbound calling, real
  ASR and TTS voices) is a documented integration and roadmap issue #1,
  not part of this build.
- Storage is in-memory. No auth. Do not expose this to a network you do
  not control.
- The grammar is English word lists and a small number parser. It will
  misunderstand real speech in ways the scripted battery cannot show.

## Run it

```
pip install -r requirements.txt
uvicorn app.main:app --port 8000
# demo UI at http://localhost:8000/
# or: docker compose up (compose file included)
```

Run the tests and the eval harness:

```
python -m pytest -q
```

## What this app has NOT proven

- That a finite-state automated check-in detects real red flags in real
  voices as well as a human caller, or faster. No such trial was found
  in the evidence audit; closing that gap needs a labelled real-patient
  pilot (issue #4) and, for any outcome claim, a trial powered on
  time-to-escalation with missed red flags as a safety endpoint.
- That it changes readmission, ED use, or any clinical outcome. The best
  synthesis says a single contact does not move readmission, and this
  repo claims nothing else.
- That the extraction grammar survives real ASR output: older voices,
  dysarthric speech, low health literacy phrasing, background noise.
  The audit flags exactly this as the open failure mode to test.
- Red-flag thresholds here are app-chosen triage lines for a proof of
  concept, not validated clinical cut-offs.

## Roadmap

1. Real telephony/PSTN integration (provider, outbound calls, real ASR/TTS)
2. EHR discharge-summary ingestion via FHIR
3. Multilingual prompt packs
4. Real-patient pilot with labelled validation
5. Persistence, auth, and audit log

## License

MIT. Author: Raphael Malikian (rtmalikian@gmail.com). Open to
collaboration with anyone working on post-discharge follow-up, and
looking for a clinical AI role.

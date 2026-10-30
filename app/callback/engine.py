"""The finite-state call engine.

States: ASKING -> (answer extracted) -> ASKING next / DONE / ESCALATED.
There is no conversational state and no branching dialogue: the machine
walks the compiled question list in order, and the only exits are
finishing the list, a red-flag answer, or two no-answers. Both exits
past the list create exactly ONE escalation task for a human.

Model-call budget, enforced by construction and asserted in tests:
  - Every answer nominal        -> template note, 0 chat calls.
  - Anything else               -> exactly 1 chat call, whose input is
    the structured answers JSON (slots and values, ~200 tokens). The
    model never sees a transcript or a raw utterance.
Prompts are rendered through the gateway speech endpoint when the
checklist is compiled, so the call itself spends no rendering time and
every render is a cache hit after the first compile of the same list.
"""
from __future__ import annotations

import json
import uuid

from app import gateway, safety
from app.callback import compiler, extract

MAX_NON_ANSWERS = 2


class CallSession:
    def __init__(self, checklist: dict, tier: str = "frugal"):
        self.checklist = checklist
        self.tier = tier
        self.session_id = uuid.uuid4().hex[:12]
        self.idx = 0
        self.answers: dict[str, dict] = {}
        self.non_answers = 0
        self.state = "asking"
        self.escalation: dict | None = None
        self.note: str | None = None
        self.llm_chat_calls = 0
        self.transcript: list[dict] = []
        self._skip_conditional()

    # -- internals ------------------------------------------------------

    def _current(self) -> dict | None:
        qs = self.checklist["questions"]
        return qs[self.idx] if self.idx < len(qs) else None

    def _skip_conditional(self) -> None:
        while True:
            q = self._current()
            if q is None:
                return
            cond = q.get("ask_if")
            if not cond:
                return
            prior = self.answers.get(cond["slot"], {})
            if prior.get("value") == cond["equals"]:
                return
            self.answers[q["slot"]] = {"status": "skipped", "value": None}
            self.idx += 1

    def _finish(self, reason: str | None) -> dict:
        self.state = "done" if reason is None else "escalated"
        chat_before = gateway.CALL_LEDGER["chat"]
        if reason is None:
            self.note = safety.render_template_note(self.answers)
        else:
            payload = {
                "answers": {slot: rec.get("value")
                            for slot, rec in self.answers.items()
                            if rec.get("status") == "answered"},
                "escalation": reason,
            }
            resp = gateway.dispatch_chat(
                [{"role": "user", "content": json.dumps(payload)}], tier=self.tier)
            draft = resp["choices"][0]["message"]["content"]
            self.note = safety.render_summary_note(self.answers, reason, draft)
            if self.tier == "full":
                # Verifier (local code, not a model call): every recorded
                # answer value must appear in the summary draft.
                missing = [s for s, r in self.answers.items()
                           if r.get("status") == "answered"
                           and str(r.get("value")) not in draft]
                self.verifier_ok = not missing
            else:
                self.verifier_ok = True
            self.escalation = {
                "task_id": uuid.uuid4().hex[:12],
                "session_id": self.session_id,
                "patient_id": self.checklist["patient_id"],
                "reason": reason,
                "answers": self.answers,
                "note": self.note,
                "assigned_to": "human clinician or staff member",
            }
        self.llm_chat_calls = gateway.CALL_LEDGER["chat"] - chat_before
        return self.record()

    # -- public API -------------------------------------------------------

    def current_prompt(self) -> dict | None:
        q = self._current()
        if q is None or self.state != "asking":
            return None
        return {"slot": q["slot"], "kind": q["kind"], "prompt": q["prompt"],
                "attempt": self.non_answers + 1}

    def answer(self, utterance: str) -> dict:
        if self.state != "asking":
            return self.record()
        q = self._current()
        rec = extract.extract_answer(q, utterance)
        entry = {"slot": q["slot"], "prompt": q["prompt"],
                 "utterance": utterance, "extracted": rec}
        self.transcript.append(entry)
        if rec["status"] == "no_answer":
            self.answers.setdefault(q["slot"], {"status": "no_answer", "value": None})
            self.non_answers += 1
            if self.non_answers >= MAX_NON_ANSWERS:
                return self._finish("non_answers")
            return self.record()
        self.answers[q["slot"]] = rec
        if compiler.is_red_flag(q, rec["value"]):
            return self._finish(f"red_flag:{q['slot']}")
        self.idx += 1
        self._skip_conditional()
        if self._current() is None:
            return self._finish(None)
        return self.record()

    def record(self) -> dict:
        return {
            "session_id": self.session_id,
            "patient_id": self.checklist["patient_id"],
            "state": self.state,
            "answers": self.answers,
            "non_answers": self.non_answers,
            "escalation": self.escalation,
            "note": self.note,
            "llm_chat_calls": self.llm_chat_calls,
            "tier": self.tier,
            "verifier_ok": getattr(self, "verifier_ok", True),
            "next_prompt": self.current_prompt(),
            "transcript": self.transcript,
        }


def run_simulated_call(checklist: dict, script: dict[str, list[str]],
                       tier: str = "frugal",
                       fallback: dict[str, str] | None = None) -> dict:
    """Run a full scripted call. `script` maps slot -> utterances, in the
    order the patient produces them for that slot; `fallback` gives a
    default utterance per slot for slots a case does not specify."""
    session = CallSession(checklist, tier=tier)
    fallback = fallback or {}
    guard = 0
    while session.state == "asking" and guard < 64:
        guard += 1
        prompt = session.current_prompt()
        if prompt is None:
            break
        slot = prompt["slot"]
        queue = script.get(slot)
        if queue:
            utterance = queue.pop(0)
        else:
            utterance = fallback.get(slot, "")
        session.answer(utterance)
    return session.record()

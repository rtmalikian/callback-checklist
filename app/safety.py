"""Safety language for Callback Checklist: PHI redaction, a banned-language
lint, and the required-language blocks every generated note must carry.

The design rule behind the lists: this product asks questions and
escalates to a human. It never interprets an answer into a diagnosis, and
it never gives treatment advice. Banned phrases are the exact strings a
note generator would produce if it slipped into either role, plus any
readmission-reduction claim, which the evidence does not support for a
single automated contact (see EVIDENCE.md). Tests scan every generated
output against this list and fail if a phrase appears.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("callback.safety")

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE", re.compile(r"(?<!\d)(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}(?!\d)")),
    ("NAME", re.compile(r"\b(?:Patient(?: Name)?|Pt\.?|Name)\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})")),
]

BANNED_PHRASES = [
    "diagnosed with",
    "you have an infection",
    "you have sepsis",
    "you have pneumonia",
    "take ibuprofen",
    "take tylenol",
    "take paracetamol",
    "take an extra dose",
    "increase your dose",
    "decrease your dose",
    "double your dose",
    "stop taking your",
    "you are fine",
    "you're fine",
    "nothing to worry about",
    "no need to call",
    "no need to see a doctor",
    "does not need review",
    "will prevent readmission",
    "prevents readmission",
    "prevent readmission",
    "reduce readmissions",
    "reduces readmission",
    "readmission risk is low",
    "low risk of readmission",
]

REQUIRED_FRAGMENTS = [
    "does not diagnose",
    "not medical advice",
    "a human",
]


def redact_phi(text: str) -> tuple[str, dict[str, int]]:
    report: dict[str, int] = {}
    redacted = text or ""
    for kind, pattern in _PATTERNS:
        redacted, n = pattern.subn(f"[{kind}]", redacted)
        if n:
            report[kind] = report.get(kind, 0) + n
    return redacted, report


def find_banned_language(text: str) -> list[str]:
    low = (text or "").lower()
    return [p for p in BANNED_PHRASES if p in low]


def missing_required_language(text: str) -> list[str]:
    low = (text or "").lower()
    return [f for f in REQUIRED_FRAGMENTS if f not in low]


def _answer_lines(answers: dict) -> str:
    lines = []
    for slot, rec in answers.items():
        if rec.get("status") == "skipped":
            lines.append(f"- {slot}: not asked (an earlier answer made it unnecessary)")
        elif rec.get("status") == "no_answer":
            lines.append(f"- {slot}: no understandable answer was recorded")
        else:
            lines.append(f"- {slot}: {rec.get('value')}")
    return "\n".join(lines) if lines else "- no answers recorded"


_CLOSING = (
    "This checklist does not diagnose any condition and is not medical advice. "
    "It asks a fixed set of questions and passes the answers on. A human "
    "clinician or staff member decides what happens next. For any medical "
    "issue or concern, seek a licensed healthcare professional. In an "
    "emergency, go to your nearest emergency room or dial 911 immediately."
)


def render_template_note(answers: dict) -> str:
    """End-of-call note when every answer is nominal. Built from a fixed
    template: zero model calls were spent on this call."""
    body = (
        "Post-discharge callback: completed. Every answer was within the "
        "checklist's expected range, so no escalation task was created.\n\n"
        "Answers recorded:\n"
        f"{_answer_lines(answers)}\n\n"
        "Note drafted from a fixed template (no model call).\n\n"
        f"{_CLOSING}"
    )
    _assert_clean(body)
    return body


def render_summary_note(answers: dict, reason: str, llm_text: str) -> str:
    """End-of-call note when the call was not fully nominal. The model
    draft is included verbatim; the framing around it is fixed template
    text, so the note can never drift into diagnosis or advice."""
    if reason.startswith("red_flag"):
        head = ("Post-discharge callback: ESCALATION. One answer crossed the "
                "checklist's red-flag line, so the call ended and this task "
                "was created for a human to act on.")
    else:
        head = ("Post-discharge callback: ESCALATION. The patient could not "
                "be understood twice, so this task was created for a human "
                "to call back and ask the questions in person.")
    body = (
        f"{head}\n\n"
        "Answers recorded:\n"
        f"{_answer_lines(answers)}\n\n"
        f"Summary draft from the structured answers:\n{llm_text}\n\n"
        "Action for staff: a human clinician or staff member should contact "
        "the patient, review these answers, and decide the next step. The "
        "checklist itself makes no such decision.\n\n"
        f"{_CLOSING}"
    )
    _assert_clean(body)
    return body


def _assert_clean(body: str) -> None:
    banned = find_banned_language(body)
    missing = missing_required_language(body)
    assert not banned, f"banned language in generated note: {banned}"
    assert not missing, f"missing required language in generated note: {missing}"

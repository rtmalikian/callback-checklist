"""Checklist compiler: discharge summary in, 5-8 fixed questions out.

The compile happens ONCE, when the patient goes home. It is a keyword
scan over a canonical question bank, not a model call: which questions
get asked must be auditable, so the mapping from summary text to
question is a rule a clinician can read. Core safety questions are
always asked. Condition-specific questions join when the summary
mentions their trigger words. The list is capped at 8 and floored at 5.

Every question carries its red-flag rule in the open. A red flag is a
triage line chosen for this proof of concept, not a diagnostic
criterion: crossing it means "a human looks now", nothing more. One
question is a probe, not a flag: reported fever opens the temperature
question, and the measured temperature carries the red line, so the
human who gets the escalation also gets the number.
"""
from __future__ import annotations

import re
import uuid

# Bank order is the asking order. kind: "yes_no" | "numeric".
# red_flag for yes_no: the answer value that escalates.
# red_flag for numeric: {"gte": x} or {"lte": x}.
BANK: list[dict] = [
    {"slot": "fever", "kind": "yes_no", "core": True, "order": 10,
     "prompt": "Since you got home, have you had a fever or chills?",
     "red_flag": {}, "probe": True, "triggers": []},
    {"slot": "temperature", "kind": "numeric", "core": True, "order": 20,
     "prompt": "What is your temperature right now, in degrees Fahrenheit?",
     "red_flag": {"gte": 100.4}, "triggers": [],
     "ask_if": {"slot": "fever", "equals": True}},
    {"slot": "breathing", "kind": "yes_no", "core": True, "order": 30,
     "prompt": "Have you had any new or worse trouble breathing since you got home?",
     "red_flag": {"answer": True}, "triggers": []},
    {"slot": "pain", "kind": "numeric", "core": True, "order": 40,
     "prompt": "On a scale of zero to ten, with ten the worst, how bad is your pain right now?",
     "red_flag": {"gte": 8}, "triggers": []},
    {"slot": "wound", "kind": "yes_no", "core": False, "order": 50,
     "prompt": "Is there any new redness, swelling, warmth, or drainage around your incision or wound?",
     "red_flag": {"answer": True},
     "triggers": ["surgery", "surgical", "incision", "stitches", "operation",
                  "wound", "appendectomy", "replacement", "bypass"]},
    {"slot": "bleeding", "kind": "yes_no", "core": False, "order": 60,
     "prompt": "Have you had any bleeding that would not stop, or blood in your vomit, urine, or stool?",
     "red_flag": {"answer": True},
     "triggers": ["blood thinner", "anticoagulant", "warfarin", "apixaban",
                  "eliquis", "surgery", "surgical", "incision", "operation"]},
    {"slot": "swelling", "kind": "yes_no", "core": False, "order": 70,
     "prompt": "Have you noticed new swelling in your legs, ankles, or feet?",
     "red_flag": {"answer": True},
     "triggers": ["heart failure", "ankle", "leg swelling", "edema",
                  "knee replacement", "hip replacement", "furosemide"]},
    {"slot": "medication", "kind": "yes_no", "core": True, "order": 80,
     "prompt": "Have you been able to take your new medicines exactly as the discharge papers say?",
     "red_flag": {"answer": False}, "triggers": []},
    {"slot": "fluids", "kind": "yes_no", "core": False, "order": 90,
     "prompt": "Have you been able to eat something and drink fluids today?",
     "red_flag": {"answer": False}, "triggers": []},
    {"slot": "dizziness", "kind": "yes_no", "core": False, "order": 100,
     "prompt": "Have you felt dizzy, faint, or confused since you got home?",
     "red_flag": {"answer": True}, "triggers": []},
    {"slot": "urination", "kind": "yes_no", "core": False, "order": 110,
     "prompt": "Have you been able to pass urine normally?",
     "red_flag": {"answer": False},
     "triggers": ["catheter", "urinary", "prostate", "urination"]},
]

MAX_QUESTIONS = 8
MIN_QUESTIONS = 5
_FILLERS = ["fluids", "dizziness"]


def compile_checklist(discharge_summary: str, patient_id: str = "anonymous") -> dict:
    """Compile a discharge summary into a fixed question list.

    The summary must already be PHI-redacted by the caller; the compiler
    only scans for trigger words and never stores the text.
    """
    text = (discharge_summary or "").lower()
    chosen: list[dict] = []
    for q in BANK:
        if q["core"]:
            chosen.append(q)
        elif any(t in text for t in q["triggers"]):
            chosen.append(q)
    if len(chosen) > MAX_QUESTIONS:
        core = [q for q in chosen if q["core"]]
        extra = [q for q in chosen if not q["core"]]
        chosen = core + extra[: MAX_QUESTIONS - len(core)]
    if len(chosen) < MIN_QUESTIONS:
        for slot in _FILLERS:
            if len(chosen) >= MIN_QUESTIONS:
                break
            q = next(b for b in BANK if b["slot"] == slot)
            if q not in chosen:
                chosen.append(q)
    chosen.sort(key=lambda q: q["order"])
    questions = []
    for q in chosen:
        item = {"slot": q["slot"], "kind": q["kind"], "prompt": q["prompt"],
                "red_flag": dict(q["red_flag"]), "core": q["core"]}
        if q.get("probe"):
            item["probe"] = True
        if "ask_if" in q:
            item["ask_if"] = dict(q["ask_if"])
        questions.append(item)
    return {"checklist_id": uuid.uuid4().hex[:12], "patient_id": patient_id,
            "questions": questions,
            "question_count": len(questions)}


def is_red_flag(question: dict, value) -> bool:
    rule = question["red_flag"]
    if not rule:
        return False  # probe question: it gates a follow-up, never flags
    if question["kind"] == "yes_no":
        return value is rule["answer"]
    if value is None:
        return False
    if "gte" in rule:
        return float(value) >= rule["gte"]
    if "lte" in rule:
        return float(value) <= rule["lte"]
    return False

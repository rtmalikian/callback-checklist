"""Callback Checklist tests: compiler, extraction grammar, finite-state
engine, model-call budget, gateway, safety language, API, and the eval
harness (red-flag recall + slot accuracy on scripted simulated calls).

The eval numbers are synthetic-fixture results (Tier 4): they prove the
pipeline does what the code says on scripted utterances. They are not
clinical accuracy and must never be quoted as such.
"""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import gateway, safety
from app.callback import compiler, engine, extract, synth
from app.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def _knee_checklist():
    return compiler.compile_checklist(synth.DEMO_SUMMARIES["knee_replacement"], "test")


# --- Compiler ---------------------------------------------------------------

def test_compile_count_bounds_and_core():
    cl = _knee_checklist()
    slots = [q["slot"] for q in cl["questions"]]
    assert 5 <= cl["question_count"] <= 8
    for core in ("fever", "temperature", "breathing", "pain", "medication"):
        assert core in slots
    for specific in ("wound", "bleeding", "swelling"):
        assert specific in slots
    assert cl["question_count"] == 8


def test_compile_plain_summary_gets_minimum():
    cl = compiler.compile_checklist(synth.DEMO_SUMMARIES["pneumonia"], "test")
    assert cl["question_count"] == 5


def test_compile_post_surgical_questions():
    cl = compiler.compile_checklist(synth.DEMO_SUMMARIES["post_surgical"], "test")
    slots = [q["slot"] for q in cl["questions"]]
    assert "wound" in slots and "bleeding" in slots and "swelling" not in slots
    assert cl["question_count"] == 7


def test_temperature_is_conditional_on_fever():
    cl = _knee_checklist()
    temp = next(q for q in cl["questions"] if q["slot"] == "temperature")
    assert temp["ask_if"] == {"slot": "fever", "equals": True}


# --- Extraction grammar -------------------------------------------------------

@pytest.mark.parametrize("text,slot,want", [
    ("Yes, I have had chills", "fever", True),
    ("No fever at all", "fever", False),
    ("Not that I know of", "fever", False),
    ("Yes, I am short of breath", "breathing", True),
    ("Breathing is fine", "breathing", False),
    ("I missed my morning dose", "medication", False),
    ("Took them all this morning", "medication", True),
    ("There is some drainage", "wound", True),
    ("No, it looks good", "wound", False),
    ("Uh, what was that?", "fever", None),
    ("The thing is, well...", "pain", None),
])
def test_extract_yes_no(text, slot, want):
    assert extract.extract_yes_no(text, slot) is want


@pytest.mark.parametrize("text,want", [
    ("101.8", 101.8),
    ("One hundred and two point four", 102.4),
    ("thirty eight point five", 38.5),
    ("Nine out of ten", 9.0),
    ("Maybe a 3 out of 10", 3.0),
    ("Around four", 4.0),
    ("Zero right now", 0.0),
    ("Hmm, say again?", None),
])
def test_extract_number(text, want):
    assert extract.extract_number(text) == want


def test_temperature_celsius_is_converted_and_labelled():
    rec = extract.extract_answer({"slot": "temperature", "kind": "numeric"},
                                 "thirty eight point five")
    assert rec["status"] == "answered"
    assert rec["value"] == 101.3
    assert rec["unit_assumed"] == "celsius"


# --- Eval harness ---------------------------------------------------------------

def run_eval():
    gateway.reset_ledger()
    checklist = _knee_checklist()
    total_red = detected_red = 0
    slots_total = slots_correct = 0
    records = {}
    for case in synth.eval_cases():
        rec = engine.run_simulated_call(checklist, case["script"],
                                        fallback=synth.NOMINAL_FALLBACK)
        records[case["name"]] = rec
        detected = bool(rec["escalation"]) and rec["escalation"]["reason"].startswith("red_flag")
        if case["expect_red_flag"]:
            total_red += 1
            detected_red += 1 if detected else 0
        for slot, want in case["expect_slots"].items():
            slots_total += 1
            got = rec["answers"].get(slot, {})
            if got.get("status") == "answered" and got.get("value") == want:
                slots_correct += 1
    return {"red_total": total_red, "red_detected": detected_red,
            "red_recall": detected_red / total_red if total_red else 1.0,
            "slots_total": slots_total, "slots_correct": slots_correct,
            "slot_accuracy": slots_correct / slots_total if slots_total else 1.0,
            "records": records}


def test_eval_red_flag_recall_and_slot_accuracy():
    m = run_eval()
    print(f"\nEVAL red-flag recall {m['red_detected']}/{m['red_total']} = {m['red_recall']:.3f}; "
          f"slot accuracy {m['slots_correct']}/{m['slots_total']} = {m['slot_accuracy']:.3f}")
    assert m["red_recall"] >= 0.95
    assert m["slot_accuracy"] >= 0.95


def test_eval_budget_per_case():
    m = run_eval()
    for name, rec in m["records"].items():
        if rec["state"] == "done":
            assert rec["llm_chat_calls"] == 0, name
        else:
            assert rec["llm_chat_calls"] == 1, name


# --- Engine behaviour -------------------------------------------------------------

def test_nominal_call_zero_model_calls_and_template_note():
    gateway.reset_ledger()
    rec = engine.run_simulated_call(_knee_checklist(), {},
                                    fallback=synth.NOMINAL_FALLBACK)
    assert rec["state"] == "done"
    assert rec["escalation"] is None
    assert rec["llm_chat_calls"] == 0
    assert "no model call" in rec["note"]


def test_red_flag_creates_exactly_one_escalation():
    rec = engine.run_simulated_call(
        _knee_checklist(), synth.persona_script("fever_high"),
        fallback=synth.NOMINAL_FALLBACK)
    assert rec["state"] == "escalated"
    assert rec["escalation"]["reason"] == "red_flag:temperature"
    assert rec["llm_chat_calls"] == 1


def test_two_non_answers_escalate_without_red_flag():
    rec = engine.run_simulated_call(
        _knee_checklist(), synth.persona_script("garbled"),
        fallback=synth.NOMINAL_FALLBACK)
    assert rec["state"] == "escalated"
    assert rec["escalation"]["reason"] == "non_answers"
    assert rec["llm_chat_calls"] == 1


def test_one_non_answer_then_clear_answer_recovers():
    rec = engine.run_simulated_call(
        _knee_checklist(), synth.persona_script("hesitant_then_clear"),
        fallback=synth.NOMINAL_FALLBACK)
    assert rec["state"] == "done"
    assert rec["non_answers"] == 1
    assert rec["llm_chat_calls"] == 0


def test_llm_payload_is_structured_answers_only(monkeypatch):
    captured = {}
    real = gateway.dispatch_chat

    def spy(messages, **kw):
        captured["messages"] = messages
        resp = real(messages, **kw)
        captured["usage"] = resp["usage"]
        return resp

    monkeypatch.setattr(gateway, "dispatch_chat", spy)
    engine.run_simulated_call(_knee_checklist(), synth.persona_script("wound_drainage"),
                              fallback=synth.NOMINAL_FALLBACK)
    content = captured["messages"][0]["content"]
    payload = json.loads(content)
    assert set(payload) == {"answers", "escalation"}
    assert "oozing" not in content and "utterance" not in content.lower()
    assert captured["usage"]["prompt_tokens"] <= 250


def test_temperature_question_skipped_when_no_fever():
    rec = engine.run_simulated_call(_knee_checklist(), {},
                                    fallback=synth.NOMINAL_FALLBACK)
    assert rec["answers"]["temperature"]["status"] == "skipped"


# --- Safety language -----------------------------------------------------------------

def test_all_eval_notes_pass_language_scans():
    m = run_eval()
    for name, rec in m["records"].items():
        assert safety.find_banned_language(rec["note"]) == [], name
        assert safety.missing_required_language(rec["note"]) == [], name


def test_phi_redaction():
    out, report = safety.redact_phi("Patient: John Smith, call 661-555-1234")
    assert "John Smith" not in out and report.get("PHONE", 0) >= 1


# --- Gateway ---------------------------------------------------------------------------

def test_speech_renders_wav_and_caches_exact_repeat():
    gateway.clear_prompt_cache()
    text = "Have you had a fever or chills since you got home, Mrs Alvarez?"
    a = gateway.dispatch_speech(text)
    b = gateway.dispatch_speech(text)
    assert a["audio"][:4] == b"RIFF" and a["cached"] is False
    assert b["cached"] is True and b["cache_kind"] == "exact"
    assert a["audio"] == b["audio"]


def test_speech_semantic_cache_reuses_near_identical_prompt():
    gateway.clear_prompt_cache()
    base = gateway.dispatch_speech(
        "Is there any new redness swelling warmth or drainage around your incision or wound")
    near = gateway.dispatch_speech(
        "Is there any new redness swelling warmth or drainage around your incision or wound today")
    assert near["cached"] is True and near["cache_kind"] in ("semantic", "exact")
    assert near["audio"] == base["audio"]


def test_chat_rejects_transcript_shaped_payload():
    with pytest.raises(Exception):
        gateway.dispatch_chat([{"role": "user",
                                "content": '{"transcript": "patient said some words"}'}])


def test_embeddings_and_models_shapes():
    emb = gateway.dispatch_embeddings(["fever question", "pain question"])
    assert emb["object"] == "list" and len(emb["data"]) == 2
    ids = {m["id"] for m in gateway.list_models()["data"]}
    assert {"callback-frugal", "callback-full", "callback-tts-1"} <= ids


# --- API ---------------------------------------------------------------------------------

def test_api_healthz_and_compile():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    r = client.post("/api/compile", json={
        "patient_id": "demo", "discharge_summary": synth.DEMO_SUMMARIES["knee_replacement"]})
    assert r.status_code == 200
    body = r.json()
    assert body["question_count"] == 8
    assert len(body["prompt_renders"]) == 8


def test_api_simulate_nominal_and_red_flag():
    r = client.post("/api/calls/simulate", json={
        "discharge_summary": synth.DEMO_SUMMARIES["post_surgical"],
        "persona": "all_nominal"})
    body = r.json()
    assert body["state"] == "done" and body["llm_chat_calls"] == 0
    r = client.post("/api/calls/simulate", json={
        "discharge_summary": synth.DEMO_SUMMARIES["post_surgical"],
        "persona": "wound_drainage"})
    body = r.json()
    assert body["state"] == "escalated"
    assert body["escalation"]["reason"] == "red_flag:wound"
    assert body["llm_chat_calls"] == 1


def test_api_step_through_call():
    r = client.post("/api/calls/start", json={
        "patient_id": "demo", "discharge_summary": synth.DEMO_SUMMARIES["pneumonia"]})
    body = r.json()
    sid = body["session_id"]
    while body["state"] == "asking":
        slot = body["next_prompt"]["slot"]
        r = client.post("/api/calls/answer", json={
            "session_id": sid, "utterance": synth.NOMINAL_FALLBACK[slot]})
        body = r.json()
    assert body["state"] == "done" and body["llm_chat_calls"] == 0


def test_api_unknown_persona_and_session():
    r = client.post("/api/calls/simulate", json={
        "discharge_summary": "x", "persona": "nobody"})
    assert r.status_code == 400
    r = client.post("/api/calls/answer", json={"session_id": "nope", "utterance": "yes"})
    assert r.status_code == 404


def test_ui_served_with_disclaimer():
    r = client.get("/")
    assert r.status_code == 200
    assert "PROOF OF CONCEPT" in r.text and "NOT CLINICALLY TESTED" in r.text


def test_readme_disclaimer_is_first():
    text = (ROOT / "README.md").read_text()
    assert text.startswith("> ## ⚠️ PROOF OF CONCEPT — NOT CLINICALLY TESTED")

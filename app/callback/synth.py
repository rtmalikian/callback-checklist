"""Simulated patients and demo discharge summaries.

v0.1.0 ships SIMULATED CALLS ONLY. A simulated patient is a script: for
each slot, the utterances it produces, in order. The scripts double as
the eval battery: every case carries ground truth (which slots hold
which values, whether a red flag is present), so the harness in
tests/ can measure red-flag recall and slot-extraction accuracy.

These are synthetic fixtures (Tier 4 in EVIDENCE.md terms). They prove
the state machine, the grammar and the budget rules do what the code
says. They say nothing about real patients, real voices, or real ASR.
"""
from __future__ import annotations

import copy

DEMO_SUMMARIES: dict[str, str] = {
    "post_surgical": (
        "Discharged home after laparoscopic appendectomy. Incision closed "
        "with stitches, keep it dry. Take acetaminophen as directed. "
        "Follow up in clinic in two weeks."
    ),
    "heart_failure": (
        "Discharged after treatment for a heart failure exacerbation. Take "
        "furosemide every morning. Weigh yourself daily and report new leg "
        "swelling or weight gain."
    ),
    "pneumonia": (
        "Discharged after treatment for pneumonia. Finish the full course "
        "of antibiotics even if you feel better. Rest, drink fluids, and "
        "follow up with your own doctor in one week."
    ),
    "knee_replacement": (
        "Discharged after total knee replacement surgery. Incision with "
        "stitches, keep the dressing clean. On apixaban, a blood thinner, "
        "and furosemide for heart failure follow-up."
    ),
}

# Default nominal utterance per slot, used when a script does not
# override the slot. Values: fever False, breathing False, pain 3,
# wound False, bleeding False, swelling False, medication True.
NOMINAL_FALLBACK: dict[str, str] = {
    "fever": "No, I feel fine",
    "temperature": "98.6",
    "breathing": "No trouble, breathing fine",
    "pain": "About a three",
    "wound": "No, it looks fine",
    "bleeding": "No bleeding at all",
    "swelling": "No swelling",
    "medication": "Yes, I took them all on schedule",
    "fluids": "Yes, eating and drinking fine",
    "dizziness": "No, I feel steady",
    "urination": "Yes, going normally",
}

_PERSONA_SCRIPTS: dict[str, dict[str, list[str]]] = {
    "all_nominal": {},
    "fever_high": {
        "fever": ["Yes, I have had chills"],
        "temperature": ["101.8"],
    },
    "severe_pain": {"pain": ["Nine out of ten"]},
    "breathing_trouble": {"breathing": ["Yes, I am short of breath"]},
    "missed_meds": {"medication": ["I missed my morning dose"]},
    "wound_drainage": {"wound": ["Yes, it is oozing a bit"]},
    "garbled": {
        "fever": ["Uh, what was that?", "The thing is, well..."],
    },
    "hesitant_then_clear": {
        "pain": ["Hmm, say again?", "About a three"],
    },
}


def persona_script(name: str) -> dict[str, list[str]]:
    return copy.deepcopy(_PERSONA_SCRIPTS[name])


def persona_names() -> list[str]:
    return list(_PERSONA_SCRIPTS)


def eval_cases() -> list[dict]:
    """The eval battery. Each case: script overrides, whether a red flag
    is truly present, and the ground-truth value of every slot the case
    pins down. Run against the knee_replacement checklist (8 questions).
    """
    cases: list[dict] = []

    def add(name, script, red, slots):
        cases.append({"name": name, "script": copy.deepcopy(script),
                      "expect_red_flag": red, "expect_slots": slots})

    # --- Fully nominal calls, three phrasing styles -------------------
    add("nominal_fallback", {}, False,
        {"fever": False, "breathing": False, "pain": 3.0, "wound": False,
         "bleeding": False, "swelling": False, "medication": True})
    add("nominal_explicit_a",
        {"fever": ["No fever at all"], "breathing": ["Breathing is fine"],
         "pain": ["Two"], "wound": ["No, it looks fine"],
         "bleeding": ["No blood at all"],
         "swelling": ["They look the same as yesterday"],
         "medication": ["I have taken every dose"]},
        False,
        {"fever": False, "breathing": False, "pain": 2.0, "wound": False,
         "bleeding": False, "swelling": False, "medication": True})
    add("nominal_explicit_b",
        {"fever": ["Not that I know of"], "breathing": ["No trouble at all"],
         "pain": ["Zero right now"], "wound": ["It looks clean and dry"],
         "bleeding": ["Nope, none"], "swelling": ["No swelling at all"],
         "medication": ["Yes, on schedule every time"]},
        False,
        {"fever": False, "breathing": False, "pain": 0.0, "wound": False,
         "bleeding": False, "swelling": False, "medication": True})

    # --- Fever / temperature ------------------------------------------
    add("fever_temp_digits",
        {"fever": ["Yes, I have had chills"], "temperature": ["101.8"]},
        True, {"fever": True, "temperature": 101.8})
    add("fever_temp_words",
        {"fever": ["Yeah, I feel hot and sweaty"],
         "temperature": ["One hundred and two point four"]},
        True, {"fever": True, "temperature": 102.4})
    add("fever_temp_celsius",
        {"fever": ["I think so, I have been sweating"],
         "temperature": ["thirty eight point five"]},
        True, {"fever": True, "temperature": 101.3})
    add("fever_temp_below_line",
        {"fever": ["Yes, since last night"],
         "temperature": ["Ninety nine point one"]},
        False, {"fever": True, "temperature": 99.1})
    add("fever_temp_just_below",
        {"fever": ["Yes, a bit of a fever"],
         "temperature": ["My thermometer says 100.2"]},
        False, {"fever": True, "temperature": 100.2})

    # --- Breathing ------------------------------------------------------
    add("breathing_short",
        {"breathing": ["Yes, I am short of breath"]},
        True, {"breathing": True})
    add("breathing_wheezy",
        {"breathing": ["I have been wheezy since morning"]},
        True, {"breathing": True})
    add("breathing_ok_variant",
        {"breathing": ["No, breathing normally"]},
        False, {"breathing": False})

    # --- Pain ------------------------------------------------------------
    add("pain_nine_words", {"pain": ["Nine out of ten"]},
        True, {"pain": 9.0})
    add("pain_eight_mixed", {"pain": ["Eight, maybe nine"]},
        True, {"pain": 8.0})
    add("pain_four", {"pain": ["Around four"]}, False, {"pain": 4.0})
    add("pain_scale_digits", {"pain": ["Maybe a 3 out of 10"]},
        False, {"pain": 3.0})

    # --- Wound -------------------------------------------------------------
    add("wound_oozing", {"wound": ["Yes, it is oozing a bit"]},
        True, {"wound": True})
    add("wound_drainage", {"wound": ["There is some drainage"]},
        True, {"wound": True})
    add("wound_red_swollen", {"wound": ["Yeah, it looks red and swollen"]},
        True, {"wound": True})
    add("wound_ok_variant", {"wound": ["No, it looks good"]},
        False, {"wound": False})

    # --- Bleeding ------------------------------------------------------------
    add("bleeding_urine", {"bleeding": ["I had blood in my urine"]},
        True, {"bleeding": True})
    add("bleeding_incision", {"bleeding": ["Yeah, some bleeding from the incision"]},
        True, {"bleeding": True})

    # --- Swelling --------------------------------------------------------------
    add("swelling_ankles", {"swelling": ["Yes, my ankles are swollen"]},
        True, {"swelling": True})
    add("swelling_some", {"swelling": ["There is some swelling"]},
        True, {"swelling": True})
    add("swelling_a_little", {"swelling": ["A little swollen, yes"]},
        True, {"swelling": True})

    # --- Medication ----------------------------------------------------------------
    add("meds_missed", {"medication": ["I missed my morning dose"]},
        True, {"medication": False})
    add("meds_ran_out", {"medication": ["No, I ran out of one of them"]},
        True, {"medication": False})
    add("meds_forgot", {"medication": ["I forgot to take them yesterday"]},
        True, {"medication": False})
    add("meds_took_variant", {"medication": ["Took them all this morning"]},
        False, {"medication": True})

    # --- No-answer handling ---------------------------------------------------------
    add("garbled_at_fever",
        {"fever": ["Uh, what was that?", "The thing is, well..."]},
        False, {})
    add("garbled_at_medication",
        {"medication": ["Well, the thing is...", "Uh, what?"]},
        False, {})
    add("hesitant_then_clear",
        {"pain": ["Hmm, say again?", "About a three"]},
        False, {"pain": 3.0})

    return cases

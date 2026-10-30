"""Answer extraction: a tiny local classifier/grammar, not a model.

Each utterance (as an ASR layer would produce it) is matched against
word lists and a small number grammar. The extractor only fills the
slot the current question asked about; it cannot wander into free-form
interpretation, which is the point. Anything it cannot classify is a
no-answer, and no-answers escalate: a patient the machine cannot
understand gets a human, not a guess.
"""
from __future__ import annotations

import re

_FILLER = {"uh", "um", "hmm", "what", "huh", "er", "ah", "well", "so",
           "the", "thing", "is", "like", "you", "know"}

# Per-slot phrase hints. present -> True, absent -> False. For the
# adherence-style slots (medication, fluids, urination) the "present"
# list holds problem phrases that mean False, so those slots set
# "problem_means_false".
_SLOT_HINTS: dict[str, dict] = {
    "fever": {
        "present": ["fever", "chills", "burning up", "feel hot", "sweating"],
        "absent": ["no fever", "temperature is normal", "feel fine", "no chills"],
    },
    "breathing": {
        "present": ["short of breath", "can't breathe", "cannot breathe",
                    "hard to breathe", "trouble breathing", "wheezy",
                    "wheezing", "breathless"],
        "absent": ["breathing fine", "breathing is fine", "breathing okay",
                   "breathing normally", "no trouble breathing"],
    },
    "wound": {
        "present": ["oozing", "drainage", "leaking", "pus", "opened up",
                    "red and swollen", "red and warm"],
        "absent": ["looks fine", "looks good", "looks clean", "dry and clean",
                   "healing fine", "healing well"],
    },
    "bleeding": {
        "present": ["bleeding", "won't stop", "would not stop", "blood in"],
        "absent": ["no blood", "bleeding stopped", "no bleeding"],
    },
    "swelling": {
        "present": ["swollen", "swelling", "puffy", "a little swollen"],
        "absent": ["no swelling", "look the same", "looks the same"],
    },
    "medication": {
        "present": ["missed", "forgot", "skipped a dose", "skipped my",
                    "ran out", "didn't take", "did not take", "haven't taken",
                    "couldn't get"],
        "absent": ["took them all", "took all", "taken them", "taking them",
                   "on schedule", "as directed", "every dose"],
        "problem_means_false": True,
    },
    "fluids": {
        "present": ["can't eat", "cannot eat", "no appetite", "haven't eaten",
                    "not drinking", "throwing up", "vomiting", "too nauseous"],
        "absent": ["eating and drinking", "ate some", "drinking fine",
                   "had breakfast", "had lunch", "had dinner"],
        "problem_means_false": True,
    },
    "dizziness": {
        "present": ["dizzy", "faint", "lightheaded", "woozy", "confused"],
        "absent": ["steady on my feet", "clear headed", "clear-headed"],
    },
    "urination": {
        "present": ["can't pee", "cannot pee", "can't urinate",
                    "cannot urinate", "haven't urinated", "not passing urine",
                    "burning when i pee"],
        "absent": ["peeing fine", "passing urine", "urinating fine",
                   "going normally"],
        "problem_means_false": True,
    },
}

_YES_TOKENS = {"yes", "yeah", "yep", "yup", "aye"}
_NO_STARTS = ("no ", "no.", "nope", "not really", "i don't", "i dont",
              "i haven't", "i havent", "i didn't", "i didnt", "never")
_NEG_TOKENS = {"no", "nope", "not", "never", "none", "nothing",
               "don't", "dont", "haven't", "havent", "didn't", "didnt",
               "hasn't", "hasnt", "can't", "cant", "cannot"}
_ADHERENCE_SLOTS = {"medication", "fluids", "urination"}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.' ]", " ", (text or "").lower())).strip()


def extract_yes_no(text: str, slot: str = "") -> bool | None:
    t = _norm(text)
    if not t:
        return None
    tokens = t.split()
    if all(tok in _FILLER for tok in tokens):
        return None
    hints = _SLOT_HINTS.get(slot, {})
    problem_false = hints.get("problem_means_false", False)
    for phrase in hints.get("absent", []):
        if phrase in t:
            return True if problem_false else False
    for phrase in hints.get("present", []):
        if phrase in t:
            return False if problem_false else True
    if any(t.startswith(s) for s in _NO_STARTS):
        return False
    if any(tok in _YES_TOKENS for tok in tokens):
        return True
    if any(tok in _NEG_TOKENS for tok in tokens):
        return False
    if slot in _ADHERENCE_SLOTS:
        if any(w in t for w in ("took", "taken", "eating", "drinking", "ate", "drank")):
            return True
    if any(w in t for w in ("a little", "a bit", "some")):
        return True
    if any(w in t for w in ("fine", "okay", "ok", "good", "normal", "better")):
        return True if slot in _ADHERENCE_SLOTS else False
    return None


_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
          "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
          "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
          "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
          "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}


def _word_number(tokens: list[str]) -> float | None:
    """Parse the first number phrase in the token stream, or None."""
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _UNITS or tok in _TENS or tok == "hundred" or tok == "a":
            # Candidate start ("a" only counts before "hundred").
            if tok == "a" and not (i + 1 < len(tokens) and tokens[i + 1] == "hundred"):
                i += 1
                continue
            value = 0.0
            seen = False
            j = i
            if j < len(tokens) and tokens[j] == "a":
                value = 1.0
                seen = True
                j += 1
            if j < len(tokens) and tokens[j] in _UNITS and tokens[j] != "zero" and value == 0.0:
                value = float(_UNITS[tokens[j]])
                seen = True
                j += 1
            if j < len(tokens) and tokens[j] == "hundred":
                value = (value or 1.0) * 100
                seen = True
                j += 1
                if j < len(tokens) and tokens[j] == "and":
                    j += 1
                if j < len(tokens) and tokens[j] in _TENS:
                    value += _TENS[tokens[j]]
                    j += 1
                    if j < len(tokens) and tokens[j] in _UNITS:
                        value += _UNITS[tokens[j]]
                        j += 1
                elif j < len(tokens) and tokens[j] in _UNITS:
                    value += _UNITS[tokens[j]]
                    j += 1
            elif j < len(tokens) and tokens[j] in _TENS:
                value += _TENS[tokens[j]]
                seen = True
                j += 1
                if j < len(tokens) and tokens[j] in _UNITS:
                    value += _UNITS[tokens[j]]
                    j += 1
            elif j < len(tokens) and tokens[j] in _UNITS:
                value = float(_UNITS[tokens[j]])
                seen = True
                j += 1
            if not seen:
                i += 1
                continue
            if j < len(tokens) and tokens[j] == "point":
                frac_digits = []
                k = j + 1
                while k < len(tokens) and (tokens[k] in _UNITS or tokens[k].isdigit()):
                    frac_digits.append(str(_UNITS[tokens[k]]) if tokens[k] in _UNITS else tokens[k])
                    k += 1
                if frac_digits:
                    value = float(f"{int(value)}.{''.join(frac_digits)}")
            return value
        i += 1
    return None


def extract_number(text: str) -> float | None:
    t = _norm(text)
    if not t:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:out of|/)\s*(?:10|ten)\b", t)
    if m:
        return float(m.group(1))
    m = re.search(r"\d+(?:\.\d+)?", t)
    if m:
        return float(m.group(0))
    return _word_number(t.split())


def extract_answer(question: dict, utterance: str) -> dict:
    """Fill one slot from one utterance. Returns a record with status
    'answered' or 'no_answer'."""
    if question["kind"] == "yes_no":
        value = extract_yes_no(utterance, question["slot"])
    else:
        value = extract_number(utterance)
        if value is not None and question["slot"] == "temperature" and value <= 45:
            # A number in the Celsius range is read as Celsius and
            # converted; the assumption is recorded, never hidden.
            return {"status": "answered", "value": round(value * 9 / 5 + 32, 1),
                    "unit_assumed": "celsius", "raw_value": value}
    if value is None:
        return {"status": "no_answer", "value": None}
    return {"status": "answered", "value": value}

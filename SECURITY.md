# SECURITY.md — Callback Checklist

## The limits, plainly

- Callback Checklist is a proof of concept. It has not been tested
  clinically, it is not a medical device, and it does not diagnose,
  treat, or rule out any condition. Its accuracy on real patients is
  unknown.
- It is a triage and escalation safety net only. It asks fixed
  questions and passes answers to a human. It never interprets an
  answer into a diagnosis and never gives treatment advice; the note
  generator's templates are linted in tests against banned diagnosis,
  treatment, and reassurance phrases.
- It does not reduce readmissions, and nothing in this repo claims it
  does. The VA synthesis of 7 RCTs found a single post-discharge
  contact within 7 days had no detectable effect on 30-day readmission
  (risk difference −0.00). See EVIDENCE.md.
- A missed red flag is the worst failure mode here. The design treats
  an answer the machine cannot understand as a reason to escalate, not
  as a pass: two no-answers create a human callback task. That reduces
  one failure mode; it does not eliminate missed detections, which is
  why real-world sensitivity is unproven until a labelled pilot exists.
- v0.1.0 runs simulated calls only. No telephone network is connected.
  Prompts from the stub backend are deterministic tone files, not a
  human-sounding voice; do not mistake the demo for a phone call.
- The extraction grammar is English word lists plus a small number
  parser. It will fail on real ASR output in ways the scripted battery
  cannot show: accents, dysarthric speech, background noise, code
  switching. Treat every extracted value as unverified.
- PHI handling in v0.1.0: discharge summaries and patient ids pass
  through a regex redactor before compiling, and the gateway ledger
  records call kinds, tiers, and token estimates only, never message
  contents, utterances, or audio. That is a demo-grade control, not a
  HIPAA programme. Storage is in-memory, there is no auth, and there
  is no audit log (roadmap issue #5). Do not deploy this with real
  patient data.
- The one model call an escalated call makes receives structured
  answers (slot names and values) only. Transcripts and raw utterances
  are never sent to the gateway; a transcript-shaped chat payload is
  rejected with HTTP 400.
- Regulatory status: none claimed. No FDA clearance, CE marking, or
  medical-device validation is implied anywhere in this repo.

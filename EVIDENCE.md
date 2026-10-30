# EVIDENCE.md — Callback Checklist

Every claim below follows the weekly-series evidence standard: Claim |
Source (full citation + link) | Tier | What it proves | What it does NOT
prove. Tier 1 = systematic review / meta-analysis / guideline /
authoritative compendium. Tier 2 = RCT / large cohort / validated
real-patient measurement study. Tier 3 = small observational / pilot.
Tier 4 = vendor / press / synthetic results, labelled as such, never
dressed as evidence.

Citation details are as recorded in the series evidence audit of
2026-10-23 (`evidence-audit-2026-10-23.md`, section 6). The VA synthesis
row was re-verified against the full text at build time (2026-10-30);
the remaining rows were search-identified in the audit and are quoted
with the audit's numbers, no more.

## The framing rule this file enforces

Callback Checklist is a **triage and escalation safety net**. It is
never framed, here or in the README, as a readmission-reduction
intervention. The reason is in the table: the strongest evidence for
readmission reduction belongs to human, multicomponent discharge
bundles, and the strongest evidence about a single early contact on its
own is null. An automated finite-state call does not inherit the bundle
effect.

## (a) The problem is real and large

| Claim | Source | Tier | Proves | Does NOT prove |
|---|---|---|---|---|
| About 1 in 5 Medicare fee-for-service patients were rehospitalised within 30 days (19.6% of 11,855,702 beneficiaries, 2003-04 claims; 34.0% within 90 days) | Jencks SF, Williams MV, Coleman EA. Rehospitalizations among patients in the Medicare fee-for-service program. *N Engl J Med.* 2009;360:1418-1428. https://pubmed.ncbi.nlm.nih.gov/19339721/ | Tier 2 (very large claims cohort) | The scale of the post-discharge problem in the landmark Medicare data | A current rate (2003-04 data; targeted-condition rates later fell), an all-payer rate, or that a phone check-in changes it |
| A median 27.1% of readmissions were deemed avoidable across 34 studies (range 5-79%), mostly by subjective single-reviewer chart review; the authors state the true proportion remains unclear | van Walraven C et al. Proportion of hospital readmissions deemed avoidable: a systematic review. *CMAJ.* 2011;183:E391-E402. https://pubmed.ncbi.nlm.nih.gov/21444623/ | Tier 1 (systematic review, high heterogeneity) | Roughly a quarter is the conventional median estimate of avoidability, with enormous uncertainty | That 27% are preventable by a phone check-in or any single intervention. The preventable factors found in follow-up work (ED decision-making, failed handover, premature discharge, goals-of-care gaps) are not all phone-addressable |
| In a single-centre cohort of 1,900 hospitalised patients (1,244 reached at 30 days), low health literacy was associated with self-reported 30-day readmission only in those aged 65 and over: AOR 3.15 (95% CI 1.77-5.61); under 65: AOR 0.78 (0.56-1.09), not significant | Jaffee EG et al. Post-discharge Falls and Readmissions: Associations with Insufficient Vision and Low Health Literacy among Hospitalized Seniors. *J Health Commun.* 2016. https://pmc.ncbi.nlm.nih.gov/articles/PMC5087130/ | Tier 2 (large single-centre observational cohort; downgrade for self-reported outcome and 35% loss to follow-up) | Why a plain-spoken, fixed-question voice check is worth testing in older patients specifically | Causation, or that a phone checklist fixes literacy-related readmission. The under-65 null result stands alongside the headline number |

## (b) The solution method, and where the evidence stops

| Claim | Source | Tier | Proves | Does NOT prove |
|---|---|---|---|---|
| **A single post-discharge contact within 7 days does not reduce 30-day readmission**: 7 RCTs, 7,075 patients, risk difference −0.00 (95% CI −0.02 to 0.02), moderate certainty of no effect; ED visits likewise RD 0.00 (5 RCTs, 3,054 patients) | Boggan JC et al. Effectiveness of Synchronous Postdischarge Contacts on Health Care Use and Patient Satisfaction: A Systematic Review and Meta-analysis (VA Evidence Synthesis Program). *Ann Intern Med.* 2025. https://pmc.ncbi.nlm.nih.gov/articles/PMC11884509/ (executive summary: https://hsrd.research.va.gov/publications/esp/pdc-exec.pdf) | Tier 1 | The central constraint on this product's claims. A callback on its own should not be expected to move readmission | That a callback is useless: the trials measured utilisation, not time-to-escalation or red-flag detection, which are this product's actual claims and remain untested |
| Bundled transitional care that includes a post-discharge component does reduce readmissions: network meta-analysis of 126 trials, 97,408 participants; low-complexity interventions OR 0.78 (0.66-0.92) for 30-day readmission | Transitional Care Interventions From Hospital to Community: systematic review and network meta-analysis. *JAMA Network Open.* https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2812390 | Tier 1 | Phone contact works as one component inside a wider, human-run bundle | That the phone component alone, or an automated version of it, carries the effect |
| Telephone follow-up as a component in older people: RR 0.84 (0.73-0.97) for readmission, in a component meta-analysis | Component meta-analysis of transitional care in older people. https://pmc.ncbi.nlm.nih.gov/articles/PMC7331096/ | Tier 1 | Same direction as the bundle finding, component level | Anything about automated or finite-state calls specifically |
| The widely quoted "31% vs 44%" programme figure is a misreading. RED (Re-Engineered Discharge) was a bundle: nurse discharge advocate, pharmacist call at 2-4 days, plain-language booklet, arranged appointments. Its result was a utilisation rate, 0.314 vs 0.451 visits per person-month (IRR 0.695, 95% CI 0.515-0.937), n = 738 RCT, driven largely by fewer ED visits | Jack BW et al. A Reengineered Hospital Discharge Program to Decrease Rehospitalization: A Randomized Trial. *Ann Intern Med.* 2009;150:178-187. https://pubmed.ncbi.nlm.nih.gov/19189907/ | Tier 2 (RCT) | What RED actually was and actually found. Cited here only to explain what this product is NOT: a lone automated call is not RED | That a pharmacist call alone, or an automated call alone, reproduces RED's result |
| Pharmacist-led transitional care (medication reconciliation, education, and human calls on days 3, 14, 30) cut the 30-day composite of readmission-or-ED visit from 39.0% to 24.8% (p = 0.01), n = 278; readmissions alone did not change significantly | Phatak A et al. Impact of pharmacist involvement in transitional care (IPITCH). *J Hosp Med.* 2016;11:39-44. https://pubmed.ncbi.nlm.nih.gov/26434752/ | Tier 2 (small RCT) | A human, multicomponent pharmacist bundle can move a composite outcome | That the call component alone works, or that an automated call works. IPITCH was human and multicomponent, and its readmission-only result was null |
| Automated IVR follow-up has repeatedly failed to move utilisation on its own: a comprehensive CHF/COPD RCT adding IVR symptom monitoring plus motivational interviewing found no difference in 30- or 90-day readmission; a cardiac-surgery IVR RCT (n = 331, 11 automated calls) found hospitalisation RR 0.77 (0.41-1.45), not significant. IVR use and acceptability were high (over 85-90%) | AJMC summary of the CHF/COPD RCT: https://www.ajmc.com/view/a-comprehensive-hospital-based-intervention-to-reduce-readmissions-for-chronically-ill-patients-a-randomized-controlled-trial ; cardiac-surgery IVR RCT via PubMed: https://pubmed.ncbi.nlm.nih.gov/19694112/ | Tier 2 (RCTs, null) | Automated voice check-ins are feasible and patients will use them; feasibility is not the open question | That IVR cannot work for triage and escalation. These trials mostly measured readmission, not red-flag detection or time-to-escalation, and tested different doses and populations |

## Honest headline for the solution method

No trial of a finite-state or automated check-in versus a human call,
measuring red-flag detection time or missed red flags, was found in the
2026-10-23 audit. The defensible claims for this product are narrow:
the same questions asked every time, an answer a human sees immediately
when it crosses a stated line, and a hard cap on model cost and model
exposure per call. Outcome claims wait for the product's own trial.

## What this app has NOT proven

Efficacy on real patients, real voices, and real phone lines is
**unproven** until a labelled real-world validation set exists (roadmap
issue #4). This app's own numbers (red-flag recall and slot accuracy on
scripted simulated patients, in the README and the test suite) are
Tier 4 synthetic-fixture results: they prove pipeline correctness only.
Specifically unproven:

- Red-flag detection in real speech, including older, dysarthric, and
  low-literacy voices, where the extraction grammar is most likely to
  fail. The audit names the required close-out: a classifier confusion
  matrix on real voices plus an escalation-threshold sensitivity
  analysis.
- Time-to-escalation versus a human call list, and any clinical outcome.
  The VA null result makes an outcome trial mandatory before any
  utilisation claim, not optional.
- The red-flag thresholds in the question bank (temperature 100.4°F,
  pain 8 of 10, and the yes/no lines) are app-chosen triage lines for
  this proof of concept. They are not validated cut-offs, and crossing
  one means "a human looks now", never a diagnosis.

# Redrob — Intelligent Candidate Discovery & Ranking

Ranks 100,000 candidate profiles against the released **Senior AI Engineer
(Founding Team)** job description, and emits a spec-compliant top-100 CSV.

The system is built to rank candidates **the way a great recruiter would** — by
reading the *work*, weighing *title against work*, sanity-checking
*plausibility*, and asking *"can I actually get this person in the room?"* — not
by counting AI keywords. It is fully **offline, CPU-only**, and ranks the whole
pool in **~25 seconds** (budget: 5 minutes, 16 GB RAM, no GPU, no network).

---

## Quick start

```bash
pip install -r requirements.txt

# Produce the submission CSV from the full pool (THE reproduce command):
python rank.py --candidates ./data/candidates.jsonl --out ./outputs/submission.csv

# Validate format against the official rules:
python validate_submission.py ./outputs/submission.csv

# Offline quality audit (honeypot rate, relevance, geography, reasoning variation):
python selftest.py --candidates ./data/candidates.jsonl --submission ./outputs/submission.csv
```

Sandbox / small-sample demo (Stage 10.5):

```bash
python app.py --candidates ./data/sample_100.jsonl --out ./outputs/sample_submission.csv --topn 20
# or, for a UI:  streamlit run app.py
```

---

## How it works

```
100K candidates
   │  stream-load + permissive structural PREFILTER  (drops obvious non-fits cheaply,
   │                                                   never discards a plausible match)
   ▼
focused working pool (~38K, ≈38% — tuned for recall; non-fits score low downstream)
   │  TF-IDF semantic similarity  vs a structured ROLE QUERY   (meaning, not keywords;
   │                                                            no model download, CPU, ms)
   ▼
interpretable JD-reading SCORE  (5 components × 2 multipliers)
   │   0.30 title/career fit      ── decisive vs keyword-stuffers; junior/intern titles demoted
   │   0.24 semantic meaning      ── lets plain-language Tier-5s rise
   │   0.18 career-text evidence  ── reads the work, catches quiet anti-signals
   │   0.16 trust-weighted skills ── endorsements + usage + proficiency + platform assessment (un-stuffable)
   │   0.12 experience-band fit   ── soft taper around 5-9 (ideal 6-8)
   │   ± small additive nudges    ── preferred-city / India relocation, product-vs-services industry
   │   × availability multiplier  ── recency, response rate, open-to-work, demand,
   │                                 github activity, notice period, interview completion
   │   × trap penalty multiplier  ── honeypot, consulting-only, title-chaser,
   │                                 CV/speech-only, recent-LLM-wrapper
   ▼
sort (score desc, candidate_id asc)  →  top 100  →  grounded per-candidate reasoning  →  CSV
```

Why TF-IDF instead of neural embeddings? The hard constraints forbid network
access and GPUs at ranking time and impose a 5-minute CPU budget. A TF-IDF
vector space over career text captures meaning beyond exact-keyword overlap
(so a candidate who "built a recommendation system at a product company" matches
the role query without ever writing "RAG"), needs zero downloads, and runs in
milliseconds. Meaning-matching is one signal among many — the title/career and
career-text components dominate, which is what defeats keyword stuffing.

See `docs/approach.pdf` for the full write-up.

## Repo layout

```
rank.py                  # main driver: load → prefilter → TF-IDF → score → CSV
app.py                   # sandbox / Streamlit demo on a small sample
selftest.py              # offline quality + format audit
validate_submission.py   # official format validator (unmodified)
src/
  role_intent.py         # structured, auditable reading of the JD (must-haves, traps, vocab)
  scoring.py             # 5 components + availability & trap multipliers
  honeypots.py           # internal-consistency checks for "subtly impossible" profiles
  reasoning.py           # grounded, varied, rank-consistent reasoning strings
data/
  candidates.jsonl       # the 100K pool (not committed; see below)
  sample_100.jsonl       # first 100, for the sandbox
outputs/
  submission.csv         # the deliverable
docs/
  approach.pdf           # methodology deck
submission_metadata.yaml # mirrors portal metadata
```

## Notes on the dataset traps (and how we handle each)

| Trap in the data | How the ranker neutralizes it |
|---|---|
| Keyword-stuffers (AI skills, wrong title) | title/career fit dominates; skills are trust-weighted, not counted |
| Honeypots (~80, "subtly impossible") | `honeypots.py` internal-consistency checks → hard down-rank; 0 in our top 100 |
| Plain-language Tier-5 (real work, no buzzwords) | TF-IDF meaning match + career-text evidence surface them |
| Title-chasers / job-hoppers | trap penalty for multiple <18-month stints |
| Consulting-only careers | trap penalty (with the JD's "ok if prior product exp" carve-out) |
| CV/speech/robotics without NLP/IR | off-domain skill drag + trap penalty when no NLP/IR text |
| Dormant / unresponsive "perfect on paper" | availability multiplier (recency × response rate × open-to-work) |

## Reproducibility

* No network and no GPU are used at ranking time.
* Output is deterministic (fixed tie-break: score desc, then `candidate_id` asc;
  TF-IDF is deterministic given fixed inputs).
* `data/candidates.jsonl` is excluded from git (size); place it under `data/`
  before running, or pass `--candidates` to your copy.

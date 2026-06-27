#!/usr/bin/env python3
"""
selftest.py — sanity & quality audit for the Redrob ranker.

Runs offline checks that don't require ground truth:
  * format validity (delegates to validate_submission.py rules)
  * honeypot rate in the top 100 (Stage-3 gate is >10% => disqualified)
  * relevance sanity: share of top 100 in ML/AI/search/recsys title families
  * geography: share in India / preferred cities
  * reasoning variation: pairwise similarity of sampled reasonings
Usage:
  python selftest.py --candidates data/candidates.jsonl --submission outputs/submission.csv
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from honeypots import is_honeypot
from role_intent import STRONG_TITLES, ADJACENT_TITLES, PREFERRED_LOCATIONS


def load_subset(path, ids):
    by = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            if c["candidate_id"] in ids:
                by[c["candidate_id"]] = c
    return by


def jaccard(a, b):
    sa, sb = set(a.lower().split()), set(b.lower().split())
    return len(sa & sb) / max(1, len(sa | sb))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--submission", required=True)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.submission, encoding="utf-8")))
    assert len(rows) == 100, f"expected 100 rows, got {len(rows)}"
    ids = [r["candidate_id"] for r in rows]
    assert len(set(ids)) == 100, "duplicate candidate_ids"
    by = load_subset(args.candidates, set(ids))
    assert all(cid in by for cid in ids), "submission references unknown candidate_id"

    # honeypot rate
    hp = [cid for cid in ids if is_honeypot(by[cid])]
    hp_rate = len(hp) / 100.0
    print(f"honeypot rate in top 100 : {hp_rate:.1%}  ({len(hp)})  "
          f"[Stage-3 gate: must be <=10%]  {'PASS' if hp_rate <= 0.10 else 'FAIL'}")

    # relevance sanity
    rel_keys = set(STRONG_TITLES) | set(ADJACENT_TITLES)
    rel = sum(1 for cid in ids
              if any(k in by[cid]["profile"]["current_title"].lower()
                     for k in rel_keys))
    print(f"relevant-title share     : {rel}/100")

    # geography
    india = sum(1 for cid in ids if by[cid]["profile"]["country"].lower() == "india")
    pref = sum(1 for cid in ids
               if any(c in by[cid]["profile"]["location"].lower()
                      for c in PREFERRED_LOCATIONS))
    print(f"India share              : {india}/100")
    print(f"preferred-city share     : {pref}/100")

    # score monotonicity
    scores = [float(r["score"]) for r in rows]
    mono = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    print(f"score non-increasing     : {'PASS' if mono else 'FAIL'}")

    # reasoning variation (sample 10, mean pairwise jaccard should be < 0.6)
    import random
    random.seed(0)
    sample = random.sample(rows, 10)
    sims = []
    for i in range(len(sample)):
        for j in range(i + 1, len(sample)):
            sims.append(jaccard(sample[i]["reasoning"], sample[j]["reasoning"]))
    mean_sim = sum(sims) / len(sims)
    print(f"reasoning mean pairwise  : {mean_sim:.2f}  "
          f"[want < 0.6 for variation]  {'PASS' if mean_sim < 0.6 else 'WARN'}")

    print("\nselftest complete.")


if __name__ == "__main__":
    main()

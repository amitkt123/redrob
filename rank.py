#!/usr/bin/env python3
"""
rank.py — Redrob Intelligent Candidate Discovery & Ranking
==========================================================
Produces a top-100 ranked CSV for the released Senior AI Engineer JD from a
candidates JSONL file, fully offline, CPU-only, within the 5-minute / 16 GB
budget.

    python rank.py --candidates data/candidates.jsonl --out outputs/submission.csv

Pipeline
--------
1. Stream-load 100K candidate records.
2. Cheap structural PREFILTER -> a focused working pool (~38K, ≈38% of the raw
   100K) of anyone with *any* plausible signal of relevance. This drops the
   clearly-irrelevant majority so the expensive steps stay well inside the time
   budget, while never discarding a real candidate (the prefilter is
   deliberately permissive — irrelevant pass-throughs score low and never reach
   the top 100, but recall is prioritised over a tighter pool).
3. Build a TF-IDF vector space over the pool's career text + the role query, and
   compute cosine similarity = the "semantic meaning" match. TF-IDF is used (not
   a neural embedding) precisely because it needs no model download, no network
   and no GPU, and runs in milliseconds on CPU — satisfying the hard constraints
   while still capturing meaning beyond exact keywords.
4. Score every pooled candidate with the interpretable JD-reading in scoring.py.
5. Sort with the spec's exact tie-break (score desc, then candidate_id asc),
   take the top 100, render reasoning, write a spec-compliant CSV.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from role_intent import (ROLE_QUERY, STRONG_TITLES, ADJACENT_TITLES,
                         CORE_RETRIEVAL_SKILLS, ML_DEPTH_SKILLS)
from scoring import score_candidate
from reasoning import build_reasoning


def _career_text(c: dict) -> str:
    p = c.get("profile", {})
    bits = [p.get("headline", ""), p.get("summary", ""),
            p.get("current_title", "")]
    for h in c.get("career_history", []) or []:
        bits.append(h.get("title", ""))
        bits.append(h.get("description", ""))
    for s in c.get("skills", []) or []:
        bits.append(s.get("name", ""))
    return " ".join(b for b in bits if b)


_RELEVANT_TITLE_KEYS = set(STRONG_TITLES) | set(ADJACENT_TITLES)


def _passes_prefilter(c: dict) -> bool:
    """
    Permissive gate: keep a candidate if ANY of these hold. The goal is to drop
    the obviously-irrelevant majority (Accountants, Civil Engineers with a couple
    of stray AI keywords) cheaply, while keeping every plausible match — including
    plain-language Tier-5s whose *title* is adjacent but whose *work* is relevant.

    This is deliberately tuned for recall, not precision: broad ML-depth skills
    (pytorch, scikit-learn, ...) and generic ranking/retrieval language let ~38%
    of the raw pool through. That is intentional — a pass-through that isn't a
    real fit scores low downstream and never reaches the top 100, whereas a
    dropped real candidate is unrecoverable. The downstream scorer, not this
    gate, does the discriminating.
    """
    p = c.get("profile", {})
    tl = (p.get("current_title", "") or "").lower()
    if any(k in tl for k in _RELEVANT_TITLE_KEYS):
        return True
    # any relevant role anywhere in history
    for h in c.get("career_history", []) or []:
        ht = (h.get("title", "") or "").lower()
        if any(k in ht for k in _RELEVANT_TITLE_KEYS):
            return True
    # any core retrieval/ML-depth skill present (catches career-changers)
    skills = {(s.get("name", "") or "").lower() for s in c.get("skills", []) or []}
    if skills & (CORE_RETRIEVAL_SKILLS | ML_DEPTH_SKILLS):
        return True
    # strong retrieval/ranking language in free text
    blob = (_career_text(c)).lower()
    if any(kw in blob for kw in ("ranking", "retrieval", "recommend",
                                 "semantic search", "vector search",
                                 "embedding", "search relevance")):
        return True
    return False


def _tfidf_similarity(pool_texts: list[str], query: str) -> list[float]:
    """Cosine similarity of each pooled candidate's text vs the role query."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    vec = TfidfVectorizer(
        lowercase=True, stop_words="english",
        ngram_range=(1, 2), min_df=2, max_df=0.9, sublinear_tf=True,
        max_features=50000,
    )
    mat = vec.fit_transform(pool_texts + [query])
    qv = mat[-1]
    docs = mat[:-1]
    sims = linear_kernel(qv, docs).ravel()
    # normalise to [0,1] across the pool for stable blending
    lo, hi = float(sims.min()), float(sims.max())
    if hi > lo:
        sims = (sims - lo) / (hi - lo)
    return sims.tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--topn", type=int, default=100)
    args = ap.parse_args()

    t0 = time.time()

    # 1. load + 2. prefilter (single streaming pass)
    pool = []
    total = 0
    with open(args.candidates, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            c = json.loads(line)
            if _passes_prefilter(c):
                pool.append(c)
    t1 = time.time()
    print(f"[load] {total} candidates, {len(pool)} passed prefilter "
          f"({t1 - t0:.1f}s)")

    # 3. semantic similarity over the pool
    pool_texts = [_career_text(c) for c in pool]
    sims = _tfidf_similarity(pool_texts, ROLE_QUERY)
    t2 = time.time()
    print(f"[tfidf] computed {len(sims)} similarities ({t2 - t1:.1f}s)")

    # 4. score
    scored = []
    for c, sim in zip(pool, sims):
        res = score_candidate(c, sim)
        scored.append((c, res))
    t3 = time.time()
    print(f"[score] scored {len(scored)} candidates ({t3 - t2:.1f}s)")

    # 5. sort with spec tie-break: score desc, candidate_id asc.
    # We sort on the *rounded* score that will actually be written to CSV, so the
    # validator's "equal scores -> candidate_id ascending" rule is satisfied
    # exactly (two scores equal at 4 dp must then order by id).
    for c, res in scored:
        res["score_r"] = round(res["score"], 4)
    scored.sort(key=lambda x: (-x[1]["score_r"], x[0]["candidate_id"]))
    top = scored[: args.topn]

    # write CSV (UTF-8, exact header, monotonic non-increasing score)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, (c, res) in enumerate(top, start=1):
            reasoning = build_reasoning(c, res)
            w.writerow([c["candidate_id"], rank,
                        f"{res['score_r']:.4f}", reasoning])
    t4 = time.time()
    print(f"[write] top {len(top)} -> {args.out} ({t4 - t3:.1f}s)")
    print(f"[done] total wall-clock {t4 - t0:.1f}s")


if __name__ == "__main__":
    main()

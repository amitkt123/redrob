#!/usr/bin/env python3
"""
app.py — minimal sandbox/demo entrypoint (Stage 10.5).

Runs the full ranking pipeline on a small candidate sample (<=100) and writes a
ranked CSV. This is the lightweight reproducibility check organizers run; the
full 100K reproduction happens from rank.py in their own sandbox.

    python app.py --candidates data/sample_100.jsonl --out outputs/sample_submission.csv

A Streamlit UI is provided if streamlit is installed (optional):
    streamlit run app.py
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run_cli(candidates, out, topn):
    cmd = [sys.executable, os.path.join(HERE, "rank.py"),
           "--candidates", candidates, "--out", out, "--topn", str(topn)]
    subprocess.run(cmd, check=True)
    print(f"\nWrote ranking to {out}")


def run_streamlit():
    import streamlit as st
    import tempfile, csv
    st.title("Redrob Candidate Ranker — Senior AI Engineer")
    st.caption("Upload a small candidates JSONL (<=100) and get a ranked shortlist.")
    up = st.file_uploader("candidates.jsonl", type=["jsonl"])
    topn = st.slider("Top N", 5, 100, 20)
    if up is not None and st.button("Rank"):
        with tempfile.NamedTemporaryFile("wb", suffix=".jsonl", delete=False) as f:
            f.write(up.read()); inpath = f.name
        outpath = inpath + ".csv"
        run_cli(inpath, outpath, topn)
        with open(outpath) as f:
            rows = list(csv.DictReader(f))
        st.dataframe(rows)
        st.download_button("Download CSV", open(outpath, "rb"),
                           file_name="ranking.csv")


def _is_streamlit():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__":
    if _is_streamlit():
        run_streamlit()
    else:
        ap = argparse.ArgumentParser()
        ap.add_argument("--candidates", default="data/sample_100.jsonl")
        ap.add_argument("--out", default="outputs/sample_submission.csv")
        ap.add_argument("--topn", type=int, default=20)
        a = ap.parse_args()
        run_cli(a.candidates, a.out, a.topn)

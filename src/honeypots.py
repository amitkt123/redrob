"""
honeypots.py
============
Detects the "subtly impossible" honeypot profiles the challenge seeds into the
pool (~80 of them, forced to relevance tier 0 in the ground truth). Ranking a
honeypot in your top 100 hurts you; >10% honeypots in the top 100 is an outright
Stage-3 disqualification.

The organisers say honeypots are findable "through careful profile inspection"
and that a good system should avoid them *naturally* rather than special-casing.
We do both: the checks below are pure internal-consistency tests — a profile is
impossible if its own numbers contradict each other. None of these checks look
at fit; they look at whether the profile *could be real*.

Observed honeypot signatures in the released pool:
  * A single job's duration_months implies more tenure than the person's total
    years_of_experience  (e.g. 166 months / 13.8 yrs at one job, 9.9 yrs total;
    or 61 months at a job for someone with 1.1 yrs total experience).
  * "expert" proficiency in a skill with 0 months of usage.
  * Sum of all job tenures vastly exceeds total experience.

Design note on precision vs recall: we deliberately do NOT use the
"skill_duration > career" rule. In this synthetic pool, skill duration_months
routinely drifts a year or two past total experience as ordinary noise (the gap
distribution is smooth and continuous, ~17k pairs over by 1-2 yrs), so that rule
flags thousands of perfectly ordinary candidates. The real honeypots miss by an
order of magnitude on *structural* facts — a job that lasted longer than the
whole career, or an expert skill never used — and those are what we catch. We
optimise for precision here because a false positive can knock a genuinely great
candidate out of the shortlist, while the JD already steers us away from the
keyword-perfect honeypots via title/career reasoning.
"""

# Tolerances are generous so we never flag a *real* candidate. Honeypots in the
# data miss by years, not months, so wide buffers keep precision high.
_EXP_BUFFER_MONTHS = 18      # slack between a duration and total career length
_TENURE_SUM_BUFFER = 36      # slack for sum-of-tenures vs total career


def honeypot_reasons(candidate: dict) -> list[str]:
    """Return a list of internal-consistency violations. Empty list => plausible."""
    reasons = []
    p = candidate.get("profile", {})
    yoe = float(p.get("years_of_experience", 0) or 0)
    career = candidate.get("career_history", []) or []
    skills = candidate.get("skills", []) or []

    exp_months = yoe * 12.0
    ceiling = exp_months + _EXP_BUFFER_MONTHS

    # 1. Any single job longer than the entire career (+buffer) is impossible.
    for h in career:
        dm = h.get("duration_months", 0) or 0
        if dm > ceiling and dm - exp_months > 24:
            reasons.append(
                f"job '{h.get('title','?')}' tenure {dm}mo > career {exp_months:.0f}mo"
            )
            break

    # 2. "expert" with zero months of usage is incoherent.
    for s in skills:
        if s.get("proficiency") == "expert" and (s.get("duration_months", None) == 0):
            reasons.append(f"expert skill '{s.get('name','?')}' with 0 months used")
            break

    # 3. Sum of all job tenures far exceeds total experience.
    total_tenure = sum((h.get("duration_months", 0) or 0) for h in career)
    if total_tenure > exp_months + _TENURE_SUM_BUFFER and total_tenure - exp_months > 60:
        reasons.append(
            f"sum of tenures {total_tenure}mo >> career {exp_months:.0f}mo"
        )

    return reasons


def is_honeypot(candidate: dict) -> bool:
    return len(honeypot_reasons(candidate)) > 0

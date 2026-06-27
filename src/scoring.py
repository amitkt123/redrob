"""
scoring.py
==========
Turns a candidate profile into (a) a fit score in [0, 1] and (b) the structured
evidence behind that score, which `reasoning.py` renders into plain English.

Philosophy
----------
A great recruiter does not count keywords. They read the *work*, weigh the
*title against the work*, sanity-check *plausibility*, and then ask "can I
actually get this person in the room?" (availability). We mirror that with five
interpretable components plus two multipliers:

  fit = semantic_meaning_match
        blended with title_career_fit
        blended with skill_evidence (trust-weighted)
        blended with experience_band_fit
        blended with eval_framework_signal
      × behavioral_availability_multiplier
      × trap_penalty_multiplier   (consulting-only, off-domain, title-chaser,
                                    recent-LangChain-only, research-only, honeypot)

Every term is bounded and explainable. No term can be gamed by stuffing the
skills array, because the skill term is trust-weighted by endorsements + usage
duration + proficiency, and because title/career evidence dominates the blend.
"""
from __future__ import annotations
import datetime
import math

from role_intent import (
    STRONG_TITLES, ADJACENT_TITLES, IRRELEVANT_TITLES,
    CORE_RETRIEVAL_SKILLS, ML_DEPTH_SKILLS, EVAL_SKILLS, OFF_DOMAIN_SKILLS,
    POSITIVE_EVIDENCE, NEGATIVE_EVIDENCE,
    CONSULTING_FIRMS, PREFERRED_LOCATIONS,
    EXP_IDEAL_LOW, EXP_IDEAL_HIGH, EXP_BAND_LOW, EXP_BAND_HIGH,
    EXP_HARD_LOW, EXP_HARD_HIGH,
)
from honeypots import honeypot_reasons

# Reference "today" for recency math — the dataset's last_active dates run into
# 2026, so we anchor to the latest plausible date rather than wall-clock now,
# keeping the ranker deterministic and reproducible offline.
_TODAY = datetime.date(2026, 6, 1)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _lower(s) -> str:
    return (s or "").lower()


def _title_fit(title: str) -> float:
    """Map a job title to a [0,1] relevance via the role family table.

    Title matching is substring-based, so "junior ml engineer" would otherwise
    inherit the full "ml engineer" weight of 1.0. The JD is a senior role, so we
    demote junior/associate/intern/entry-level titles: the substance may still be
    relevant, but the seniority is a genuine mismatch the score must reflect.
    """
    t = _lower(title)
    junior_modifier = 0.65 if any(j in t for j in (
        "junior", "associate", "intern", "entry", "trainee", "fresher",
        "graduate engineer", "apprentice")) else 1.0
    best = 0.0
    for key, w in STRONG_TITLES.items():
        if key in t:
            best = max(best, w)
    for key, w in ADJACENT_TITLES.items():
        if key in t:
            best = max(best, w)
    if best > 0.0:
        return best * junior_modifier
    # exact irrelevant title with no stronger match => near zero
    for key in IRRELEVANT_TITLES:
        if key == t or key in t:
            return 0.05
    return best


def _proficiency_weight(p: str) -> float:
    return {"beginner": 0.3, "intermediate": 0.6,
            "advanced": 0.85, "expert": 1.0}.get(p, 0.5)


# ---------------------------------------------------------------------------
# component scores
# ---------------------------------------------------------------------------
def title_career_fit(candidate: dict) -> tuple[float, dict]:
    """
    Blend current-title relevance with the *best* and *recent* roles in the
    career history. This is the decisive guard against the keyword-stuffer trap:
    a "Marketing Manager" whose skills array is full of AI terms still scores low
    here, because neither their title nor their actual roles are relevant.
    """
    p = candidate.get("profile", {})
    cur = _title_fit(p.get("current_title", ""))

    career = candidate.get("career_history", []) or []
    role_scores = []
    for h in career:
        tf = _title_fit(h.get("title", ""))
        # recency & duration weighting: recent, substantial roles matter more
        recency = 1.3 if h.get("is_current") else 1.0
        dur = h.get("duration_months", 0) or 0
        dur_w = min(1.0, 0.4 + dur / 36.0)   # saturates ~3 yrs
        role_scores.append(tf * recency * dur_w)
    best_role = max(role_scores) if role_scores else 0.0
    best_role = min(1.0, best_role)

    score = 0.55 * cur + 0.45 * best_role
    return score, {"current_title_fit": round(cur, 3),
                   "best_role_fit": round(best_role, 3)}


def skill_evidence(candidate: dict) -> tuple[float, dict]:
    """
    Trust-weighted skill match. Each relevant skill contributes proportionally to
    a *trust* factor = f(endorsements, usage-months, proficiency), so a list of
    'expert' skills with no endorsements and no usage contributes almost nothing.
    Off-domain (CV/speech/robotics) skills add a small penalty, per the JD.
    """
    skills = candidate.get("skills", []) or []
    sig = candidate.get("redrob_signals", {}) or {}
    # Platform-verified assessment scores (skill_name -> 0..100). These are far
    # more trustworthy than a self-declared proficiency, so a skill the candidate
    # actually scored well on gets its trust factor lifted; a skill they scored
    # poorly on is tempered. Keyed case-insensitively for robust name matching.
    assess = {str(k).lower(): float(v)
              for k, v in (sig.get("skill_assessment_scores") or {}).items()
              if isinstance(v, (int, float))}
    core = depth = eval_ = 0.0
    off = 0.0
    core_names = []
    assessed_hits = 0
    for s in skills:
        name = _lower(s.get("name", ""))
        endo = s.get("endorsements", 0) or 0
        dur = s.get("duration_months", 0) or 0
        prof = _proficiency_weight(s.get("proficiency", ""))
        # trust in (0,1]: needs some endorsements AND real usage to count fully
        trust = prof * (0.45 + 0.30 * min(1.0, endo / 20.0)
                        + 0.25 * min(1.0, dur / 24.0))
        # platform-verified assessment adjusts trust toward measured reality:
        # a 100/100 lifts trust ~25%, a 0/100 halves it; centred at ~60/100.
        if name in assess:
            assessed_hits += 1
            trust *= max(0.5, min(1.25, 0.7 + 0.55 * (assess[name] / 100.0)))
        if name in CORE_RETRIEVAL_SKILLS:
            core += trust; core_names.append(s.get("name"))
        elif name in ML_DEPTH_SKILLS:
            depth += trust
        if name in EVAL_SKILLS:
            eval_ += trust
        if name in OFF_DOMAIN_SKILLS:
            off += 0.5 * prof
    # saturating combination — diminishing returns, can't be farmed
    core_s = 1.0 - math.exp(-core / 2.0)
    depth_s = 1.0 - math.exp(-depth / 3.0)
    eval_s = 1.0 - math.exp(-eval_ / 1.0)
    raw = 0.55 * core_s + 0.30 * depth_s + 0.15 * eval_s
    off_pen = min(0.25, 0.05 * off)          # bounded off-domain drag
    score = max(0.0, raw - off_pen)
    return score, {"core_skill_hits": len(core_names),
                   "core_skills": core_names[:6],
                   "eval_signal": round(eval_s, 2),
                   "assessed_skill_hits": assessed_hits,
                   "offdomain_drag": round(off_pen, 2)}


def career_text_evidence(candidate: dict) -> tuple[float, dict]:
    """
    Read the free-text of every role + the summary for proof of real
    retrieval/ranking/recsys/eval work — and for quiet anti-signals. This is how
    a 'plain-language Tier-5' (built a recommender, never said 'RAG') surfaces,
    and how an ML-titled candidate who only did 'lighter-weight' work is tempered.
    """
    p = candidate.get("profile", {})
    blob = _lower(p.get("summary", "")) + " "
    for h in candidate.get("career_history", []) or []:
        blob += _lower(h.get("description", "")) + " "
    pos = sum(1 for kw in POSITIVE_EVIDENCE if kw in blob)
    neg = sum(1 for kw in NEGATIVE_EVIDENCE if kw in blob)
    pos_s = 1.0 - math.exp(-pos / 4.0)
    neg_pen = min(0.30, 0.12 * neg)
    score = max(0.0, pos_s - neg_pen)
    return score, {"positive_evidence_hits": pos,
                   "negative_evidence_hits": neg}


def experience_fit(candidate: dict) -> tuple[float, dict]:
    """Soft band around the JD's 5-9 (ideal 6-8), tapering rather than cutting."""
    yoe = float(candidate.get("profile", {}).get("years_of_experience", 0) or 0)
    if EXP_IDEAL_LOW <= yoe <= EXP_IDEAL_HIGH:
        s = 1.0
    elif EXP_BAND_LOW <= yoe <= EXP_BAND_HIGH:
        s = 0.9
    elif EXP_HARD_LOW <= yoe <= EXP_HARD_HIGH:
        # linear taper toward the hard edges
        if yoe < EXP_BAND_LOW:
            s = 0.5 + 0.4 * (yoe - EXP_HARD_LOW) / (EXP_BAND_LOW - EXP_HARD_LOW)
        else:
            s = 0.5 + 0.4 * (EXP_HARD_HIGH - yoe) / (EXP_HARD_HIGH - EXP_BAND_HIGH)
    else:
        s = 0.25
    return s, {"years_of_experience": yoe}


# ---------------------------------------------------------------------------
# behavioral availability multiplier  (JD: "not actually available -> downweight")
# ---------------------------------------------------------------------------
def availability_multiplier(candidate: dict) -> tuple[float, dict]:
    sig = candidate.get("redrob_signals", {}) or {}
    notes = {}

    # recency of last activity
    try:
        la = datetime.date.fromisoformat(sig.get("last_active_date", ""))
        days = (_TODAY - la).days
    except Exception:
        days = 365
    recency = 1.0 if days <= 30 else (0.85 if days <= 90 else
              (0.65 if days <= 180 else 0.45))

    resp = float(sig.get("recruiter_response_rate", 0) or 0)       # 0..1
    resp_f = 0.6 + 0.4 * resp                                       # 0.6..1.0
    otw = 1.0 if sig.get("open_to_work_flag") else 0.85
    completeness = float(sig.get("profile_completeness_score", 0) or 0) / 100.0
    comp_f = 0.9 + 0.1 * completeness

    # demand signals (recruiters saving / searching) — mild positive
    saved = sig.get("saved_by_recruiters_30d", 0) or 0
    demand_f = 1.0 + 0.05 * min(1.0, saved / 10.0)

    # github activity (0..100, -1 if no GitHub) — small corroboration of a real,
    # active engineer. Neutral (no penalty) when unlinked, since absence of a
    # GitHub is not evidence of low quality for a senior hire.
    gh = float(sig.get("github_activity_score", -1) or -1)
    github_f = 1.0 + 0.05 * (gh / 100.0) if gh >= 0 else 1.0

    # notice period (days, 0..180) — practical availability. Short notice is a
    # mild plus; long notice a mild drag. Bounded so it never dominates.
    notice = sig.get("notice_period_days", None)
    if notice is None:
        notice_f = 1.0
    else:
        nd = float(notice)
        notice_f = (1.0 if nd <= 30 else 0.97 if nd <= 60
                    else 0.93 if nd <= 90 else 0.88)

    # interview completion rate (0..1) — predicts whether interviews actually
    # happen once scheduled. Folded in mildly.
    icr = sig.get("interview_completion_rate", None)
    interview_f = (0.9 + 0.1 * float(icr)) if icr is not None else 1.0

    mult = (recency * resp_f * otw * comp_f * demand_f
            * github_f * notice_f * interview_f)
    mult = max(0.40, min(1.10, mult))
    notes.update(response_rate=round(resp, 2), days_since_active=days,
                 open_to_work=bool(sig.get("open_to_work_flag")),
                 notice_period_days=(int(notice) if notice is not None else None),
                 github_activity=(round(gh, 1) if gh >= 0 else None))
    return mult, notes


# ---------------------------------------------------------------------------
# trap / disqualifier penalty multiplier  (JD: "things we explicitly do NOT want")
# ---------------------------------------------------------------------------
def trap_penalty(candidate: dict) -> tuple[float, list[str]]:
    flags = []
    mult = 1.0
    p = candidate.get("profile", {})
    career = candidate.get("career_history", []) or []

    # Honeypot => hard kill (these are tier-0 in ground truth).
    if honeypot_reasons(candidate):
        flags.append("honeypot:" + honeypot_reasons(candidate)[0])
        return 0.02, flags

    # Consulting-only career (no product company anywhere).
    companies = [_lower(h.get("company", "")) for h in career]
    cur_co = _lower(p.get("current_company", ""))
    all_co = companies + [cur_co]
    is_consult = lambda c: any(f in c for f in CONSULTING_FIRMS)
    if all_co and all(is_consult(c) for c in all_co if c):
        flags.append("consulting-only career")
        mult *= 0.45
    elif is_consult(cur_co):
        flags.append("currently at consulting firm")
        mult *= 0.85   # JD: ok if prior product experience exists

    # Title-chaser: many short stints (<=18 months) across companies.
    short = sum(1 for h in career
                if 0 < (h.get("duration_months", 0) or 0) <= 18
                and not h.get("is_current"))
    if len(career) >= 3 and short >= 3:
        flags.append("job-hopping pattern (multiple <18mo stints)")
        mult *= 0.80

    # Off-domain primary expertise (CV/speech/robotics) with no NLP/IR text.
    blob = _lower(p.get("summary", ""))
    for h in career:
        blob += " " + _lower(h.get("description", ""))
    off_terms = ["computer vision", "image", "speech", "robotic", "object detection"]
    nlp_terms = ["nlp", "language", "retrieval", "search", "ranking",
                 "recommend", "embedding", "text"]
    if any(t in blob for t in off_terms) and not any(t in blob for t in nlp_terms):
        flags.append("primary CV/speech/robotics, little NLP/IR")
        mult *= 0.70

    # Recent-LangChain-only with thin experience (proxy for the JD anti-pattern).
    yoe = float(p.get("years_of_experience", 0) or 0)
    skills = [_lower(s.get("name", "")) for s in candidate.get("skills", []) or []]
    if "langchain" in skills and yoe < 3.5 and "retrieval" not in blob:
        flags.append("thin recent-LLM-wrapper profile")
        mult *= 0.80

    return mult, flags


# ---------------------------------------------------------------------------
# location bonus (small additive nudge, not a gate — JD is "preferred/flexible")
# ---------------------------------------------------------------------------
def location_bonus(candidate: dict) -> tuple[float, dict]:
    p = candidate.get("profile", {})
    loc = _lower(p.get("location", ""))
    country = _lower(p.get("country", ""))
    sig = candidate.get("redrob_signals", {}) or {}
    relo = sig.get("willing_to_relocate", False)
    in_pref = any(c in loc for c in PREFERRED_LOCATIONS)
    bonus = 0.0
    note = {}
    if in_pref:
        bonus = 0.05; note["location"] = "in preferred city"
    elif country == "india" and relo:
        bonus = 0.03; note["location"] = "India + willing to relocate"
    elif country == "india":
        bonus = 0.0; note["location"] = "India, relocation unclear"
    else:
        bonus = -0.04; note["location"] = "outside India (no visa sponsorship)"
    return bonus, note


# ---------------------------------------------------------------------------
# company-context nudge (small additive — JD prefers product over services)
# ---------------------------------------------------------------------------
# Industry strings that read as product/tech work the JD prefers.
_PRODUCT_INDUSTRIES = (
    "product", "software", "internet", "saas", "technology", "fintech",
    "e-commerce", "ecommerce", "ai", "machine learning", "platform",
    "consumer", "marketplace",
)
# Industry strings that read as services/consulting/staffing (de-emphasised; the
# heavier consulting penalty already lives in trap_penalty for pure-consulting).
_SERVICES_INDUSTRIES = (
    "it services", "consulting", "staffing", "outsourcing", "bpo",
    "system integrator", "services",
)


def company_context_bonus(candidate: dict) -> tuple[float, dict]:
    """Tiny additive nudge from current industry. Bounded to ±0.03 so it only
    breaks ties between otherwise-comparable candidates — the JD's product-vs-
    services preference, not a primary signal (which trap_penalty handles)."""
    p = candidate.get("profile", {})
    ind = _lower(p.get("current_industry", ""))
    note = {}
    bonus = 0.0
    if ind:
        if any(t in ind for t in _SERVICES_INDUSTRIES):
            bonus = -0.03
            note["company_context"] = "services/IT-consulting industry"
        elif any(t in ind for t in _PRODUCT_INDUSTRIES):
            bonus = 0.03
            note["company_context"] = "product/tech industry"
    return bonus, note


# ---------------------------------------------------------------------------
# top-level
# ---------------------------------------------------------------------------
def score_candidate(candidate: dict, semantic_sim: float) -> dict:
    """
    Combine all components. `semantic_sim` is the precomputed TF-IDF cosine in
    [0,1] between the candidate's career text and the role query (computed in
    bulk in rank.py for speed).
    """
    tc, tc_d = title_career_fit(candidate)
    sk, sk_d = skill_evidence(candidate)
    ev, ev_d = career_text_evidence(candidate)
    ex, ex_d = experience_fit(candidate)
    avail, av_d = availability_multiplier(candidate)
    pen, flags = trap_penalty(candidate)
    loc_b, loc_d = location_bonus(candidate)
    co_b, co_d = company_context_bonus(candidate)

    # Core fit blend. Title/career and semantic meaning dominate; skills are
    # supporting evidence (deliberately, to defeat keyword stuffing). The
    # career-text evidence lets plain-language strong candidates rise.
    base = (0.30 * tc
            + 0.24 * semantic_sim
            + 0.18 * ev
            + 0.16 * sk
            + 0.12 * ex)
    base = min(1.0, max(0.0, base + loc_b + co_b))

    final = base * avail * pen
    final = max(0.0, min(1.0, final))

    return {
        "score": final,
        "base": base,
        "semantic_sim": round(semantic_sim, 3),
        "components": {**tc_d, **sk_d, **ev_d, **ex_d, **av_d, **loc_d, **co_d,
                       "experience_fit": round(ex, 2),
                       "availability_mult": round(avail, 2),
                       "trap_mult": round(pen, 2)},
        "flags": flags,
    }

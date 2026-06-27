#!/usr/bin/env python3
"""Generate docs/approach.pdf — the methodology deck (slide-style PDF)."""
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, PageBreak, ListFlowable,
                                ListItem)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

PAGE = landscape(A4)
W, H = PAGE

INK = colors.HexColor("#1a1f2b")
ACCENT = colors.HexColor("#e2483d")        # redrob-ish red
ACCENT2 = colors.HexColor("#2f6df0")
MUTE = colors.HexColor("#5b6472")
LIGHT = colors.HexColor("#f3f5f8")
LINE = colors.HexColor("#d9dee6")

styles = getSampleStyleSheet()
def S(name, **kw):
    base = kw.pop("parent", styles["Normal"])
    return ParagraphStyle(name, parent=base, **kw)

TITLE = S("T", fontName="Helvetica-Bold", fontSize=30, textColor=INK, leading=34)
SUB = S("Sub", fontName="Helvetica", fontSize=14, textColor=MUTE, leading=18)
H1 = S("H1", fontName="Helvetica-Bold", fontSize=22, textColor=INK, leading=26,
       spaceAfter=10)
KICK = S("K", fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT,
         leading=13, spaceAfter=2)
BODY = S("B", fontName="Helvetica", fontSize=11.5, textColor=INK, leading=16)
BODYW = S("BW", fontName="Helvetica", fontSize=11, textColor=colors.white, leading=15)
SMALL = S("Sm", fontName="Helvetica", fontSize=9.5, textColor=MUTE, leading=13)
BULLET = S("Bu", fontName="Helvetica", fontSize=11.5, textColor=INK, leading=15)
CODE = S("C", fontName="Courier", fontSize=10, textColor=INK, leading=13)


def bullets(items, st=BULLET, color=ACCENT):
    return ListFlowable(
        [ListItem(Paragraph(t, st), leftIndent=10, value="•") for t in items],
        bulletType="bullet", bulletColor=color, bulletFontSize=11,
        leftIndent=14, spaceBefore=2, spaceAfter=2,
    )


class Deck(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=PAGE,
                         leftMargin=1.6*cm, rightMargin=1.6*cm,
                         topMargin=1.5*cm, bottomMargin=1.3*cm)
        frame = Frame(self.leftMargin, self.bottomMargin,
                      W - self.leftMargin - self.rightMargin,
                      H - self.topMargin - self.bottomMargin, id="main")
        self.addPageTemplates([PageTemplate(id="p", frames=[frame],
                                            onPage=self._chrome)])
        self.page_no = 0

    def _chrome(self, c, doc):
        c.saveState()
        c.setFillColor(ACCENT)
        c.rect(0, H - 0.35*cm, W, 0.35*cm, stroke=0, fill=1)
        c.setFont("Helvetica", 8)
        c.setFillColor(MUTE)
        c.drawString(1.6*cm, 0.7*cm, "Redrob · Intelligent Candidate Discovery & Ranking")
        c.drawRightString(W - 1.6*cm, 0.7*cm, "Senior AI Engineer (Founding Team)")
        c.restoreState()


def card(title, body_flowables, w, bg=LIGHT, tcolor=INK):
    inner = [Paragraph(title, S("ct", fontName="Helvetica-Bold", fontSize=12.5,
                                textColor=tcolor, leading=15, spaceAfter=5))]
    inner += body_flowables
    t = Table([[inner]], colWidths=[w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def build():
    story = []

    # ---------- Slide 1: title ----------
    story.append(Spacer(1, 2.2*cm))
    story.append(Paragraph("Reading the role, not the keywords", KICK))
    story.append(Paragraph("Intelligent Candidate Discovery &amp; Ranking", TITLE))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "An interpretable, recruiter-grade ranker for the Senior AI Engineer "
        "(Founding Team) role — fully offline, CPU-only, ~25s over 100,000 "
        "profiles.", SUB))
    story.append(Spacer(1, 0.8*cm))
    chips = Table([[
        Paragraph("0 honeypots<br/>in top 100", BODYW),
        Paragraph("100% relevant<br/>titles in top 100", BODYW),
        Paragraph("96% India ·<br/>51% preferred city", BODYW),
        Paragraph("~25s / 100K ·<br/>no GPU · no network", BODYW),
    ]], colWidths=[6.2*cm]*4)
    chips.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), ACCENT),
        ("BACKGROUND", (1, 0), (1, 0), ACCENT2),
        ("BACKGROUND", (2, 0), (2, 0), INK),
        ("BACKGROUND", (3, 0), (3, 0), MUTE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(chips)
    story.append(PageBreak())

    # ---------- Slide 2: the problem / insight ----------
    story.append(Paragraph("The problem is a reading-comprehension problem", H1))
    story.append(Paragraph(
        "The JD is written to defeat keyword matchers. It explicitly says: "
        "<i>“the right answer is NOT to find candidates whose skills section "
        "contains the most AI keywords — that’s a trap we built into the "
        "dataset.”</i> So the task isn’t search; it’s reasoning about the gap "
        "between what the JD <b>says</b> and what it <b>means</b>.", BODY))
    story.append(Spacer(1, 0.4*cm))
    row = Table([[
        card("What the JD literally lists", [bullets([
            "Embeddings retrieval, vector DBs, hybrid search",
            "Strong Python, ranking-eval frameworks",
            "5–9 years; LLM fine-tuning (nice-to-have)",
        ], color=MUTE)], 12.5*cm),
        card("What the JD actually means", [bullets([
            "Has <b>shipped</b> ranking/search/recsys to real users at a product company",
            "Tilts shipper over researcher; writes production code now",
            "Reachable: active, responsive, in/near Pune–Noida",
            "NOT: keyword-stuffers, consulting-only, title-chasers, CV/speech-only",
        ], color=ACCENT)], 12.5*cm),
    ]], colWidths=[12.9*cm, 12.9*cm])
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (0, 0), 8)]))
    story.append(row)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Design consequence: title/career evidence and the <i>meaning</i> of the "
        "work must outweigh the skills array — and plausibility + availability "
        "must gate everything.", SMALL))
    story.append(PageBreak())

    # ---------- Slide 3: architecture ----------
    story.append(Paragraph("Architecture — a transparent funnel", H1))
    pipe = [
        ("100,000 candidates", "stream-load, one pass", INK),
        ("Permissive prefilter", "drop obvious non-fits cheaply; never lose a plausible match", ACCENT2),
        ("TF-IDF semantic match", "career text vs a structured role query — meaning, not keywords", ACCENT2),
        ("Interpretable score", "5 components × availability × trap penalty", ACCENT),
        ("Top-100 + reasoning", "spec tie-break, grounded explanations, CSV", INK),
    ]
    data = [[Paragraph(f"<b>{a}</b>", BODYW), Paragraph(b, BODYW)] for a, b, _ in pipe]
    t = Table(data, colWidths=[6.5*cm, 18.2*cm])
    sty = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
           ("LEFTPADDING", (0, 0), (-1, -1), 12),
           ("TOPPADDING", (0, 0), (-1, -1), 9),
           ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
           ("LINEBELOW", (0, 0), (-1, -1), 3, colors.white)]
    for i, (_, _, col) in enumerate(pipe):
        sty.append(("BACKGROUND", (0, i), (0, i), col))
        sty.append(("BACKGROUND", (1, i), (1, i), colors.HexColor("#3a4252")))
    t.setStyle(TableStyle(sty))
    story.append(t)
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Why TF-IDF and not a neural embedding?", KICK))
    story.append(Paragraph(
        "The constraints forbid network and GPU at ranking time and cap runtime "
        "at 5 min on CPU. TF-IDF over career text captures meaning beyond exact "
        "keyword overlap (a candidate who “built a recommendation system at a "
        "product company” matches the role query without ever writing “RAG”), "
        "needs zero downloads, and runs in milliseconds. Meaning is one signal "
        "among many — title/career and career-text evidence dominate the blend, "
        "which is what actually defeats keyword stuffing.", BODY))
    story.append(PageBreak())

    # ---------- Slide 4: the score ----------
    story.append(Paragraph("The score — five readable components, two multipliers", H1))
    comp = [
        ["Component", "Wt", "What it reads", "Why it matters"],
        ["Title / career fit", "0.30", "current title + best/recent roles, duration-weighted",
         "Decisive guard vs keyword-stuffers — a ‘Marketing Manager’ with AI skills still scores ~0"],
        ["Semantic meaning", "0.24", "TF-IDF cosine vs role query",
         "Surfaces plain-language Tier-5s who did the work without the buzzwords"],
        ["Career-text evidence", "0.18", "free-text of every role + summary",
         "Reads the work; catches quiet anti-signals (‘lighter weight than ranking’)"],
        ["Trust-weighted skills", "0.16", "endorsements × usage × proficiency",
         "Un-stuffable: a list of ‘expert’ skills with no usage/endorsements counts for almost nothing"],
        ["Experience band", "0.12", "soft taper around 5–9 (ideal 6–8)",
         "A range, not a cutoff — strong outliers still rank, with an honest concern noted"],
        ["× Availability", "mult", "recency, response rate, open-to-work, demand",
         "‘Perfect on paper but dormant / 5% response’ → not actually hireable → down-weighted"],
        ["× Trap penalty", "mult", "honeypot, consulting-only, hopper, CV/speech-only, LLM-wrapper",
         "Encodes the JD’s explicit ‘do NOT want’ list; honeypots are forced to ~0"],
    ]
    t = Table(comp, colWidths=[3.8*cm, 1.3*cm, 6.6*cm, 13.0*cm])
    ts = [("BACKGROUND", (0, 0), (-1, 0), INK),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
          ("FONTNAME", (0, 1), (1, -1), "Helvetica-Bold"),
          ("FONTSIZE", (0, 0), (-1, -1), 9.3),
          ("TEXTCOLOR", (0, 1), (-1, -1), INK),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("LEFTPADDING", (0, 0), (-1, -1), 7),
          ("RIGHTPADDING", (0, 0), (-1, -1), 7),
          ("TOPPADDING", (0, 0), (-1, -1), 6),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
          ("GRID", (0, 0), (-1, -1), 0.4, LINE),
          ("ROWBACKGROUNDS", (0, 1), (-1, 5), [colors.white, LIGHT]),
          ("BACKGROUND", (0, 6), (-1, 7), colors.HexColor("#fdeceb")),
          ("LINEABOVE", (0, 6), (-1, 6), 1, ACCENT)]
    # wrap long cells as paragraphs
    for r in range(1, len(comp)):
        comp[r][2] = Paragraph(comp[r][2], SMALL)
        comp[r][3] = Paragraph(comp[r][3], SMALL)
    t = Table(comp, colWidths=[3.8*cm, 1.3*cm, 6.6*cm, 13.0*cm])
    t.setStyle(TableStyle(ts))
    story.append(t)
    story.append(Spacer(1, 0.25*cm))
    story.append(Paragraph(
        "fit = (0.30·title/career + 0.24·meaning + 0.18·text-evidence + "
        "0.16·skills + 0.12·experience + location) × availability × trap", CODE))
    story.append(PageBreak())

    # ---------- Slide 5: traps ----------
    story.append(Paragraph("Every trap in the dataset, and how it’s neutralized", H1))
    trap = [
        ["Trap", "Mechanism that handles it"],
        ["Keyword-stuffers (AI skills, wrong title)",
         "Title/career fit dominates; skills are trust-weighted, not counted"],
        ["Honeypots (~80, ‘subtly impossible’)",
         "Internal-consistency checks (job/skill tenure &gt; whole career; expert+0 months) → forced down"],
        ["Plain-language Tier-5 (real work, no buzzwords)",
         "TF-IDF meaning match + career-text evidence surface them"],
        ["Title-chasers / job-hoppers",
         "Penalty for multiple sub-18-month stints"],
        ["Consulting-only careers",
         "Penalty, with the JD’s ‘OK if prior product experience’ carve-out"],
        ["CV / speech / robotics without NLP/IR",
         "Off-domain skill drag + penalty when no NLP/IR appears in the text"],
        ["Dormant ‘perfect on paper’",
         "Availability multiplier: recency × response rate × open-to-work"],
    ]
    for r in range(1, len(trap)):
        trap[r][0] = Paragraph(trap[r][0], S("tl", parent=SMALL, fontName="Helvetica-Bold", textColor=INK))
        trap[r][1] = Paragraph(trap[r][1], SMALL)
    t = Table(trap, colWidths=[9.5*cm, 15.2*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Honeypot detection optimizes for <b>precision</b> (wide tolerances) — a "
        "false positive would knock out a real candidate, and the JD reasoning "
        "already buries the keyword-perfect honeypots via title/career fit.", SMALL))
    story.append(PageBreak())

    # ---------- Slide 6: results + reasoning ----------
    story.append(Paragraph("Results &amp; the reasoning layer", H1))
    left = card("Top-100 audit (offline, no ground truth)", [bullets([
        "<b>0</b> honeypots in top 100 (Stage-3 gate: &lt;10%)",
        "<b>100/100</b> in ML/AI/search/recsys title families",
        "<b>96/100</b> in India · <b>51/100</b> in preferred cities",
        "Scores strictly non-increasing; format validator: PASS",
        "Runtime ~25s for 100K on CPU, no network",
    ], color=ACCENT2)], 12.5*cm)
    right = card("Reasoning is grounded, varied, rank-consistent", [
        Paragraph("Every clause comes only from the candidate’s own record — no "
                  "hallucinated skills. Tone tracks the score, and phrasing is "
                  "deterministically varied (mean pairwise similarity 0.23), so "
                  "Stage-4 review sees specific, honest, non-templated text.", SMALL),
        Spacer(1, 0.2*cm),
        Paragraph("Rank 1 — 0.91", KICK),
        Paragraph("“Strong fit: Staff Machine Learning Engineer, 7.0 yrs — depth "
                  "in Semantic Search, pgvector, Pinecone, BM25; production "
                  "search/recsys at scale; open to relocating to Pune/Noida.”",
                  SMALL),
        Spacer(1, 0.15*cm),
        Paragraph("Rank 6 — 0.81 (honest concern surfaced)", KICK),
        Paragraph("“Strong fit: Senior Applied Scientist, 16.2 yrs — track record "
                  "of applied retrieval and ranking… Concern: experience 16.2y "
                  "above the 5–9 band.”", SMALL),
    ], 12.5*cm, bg=colors.white)
    row = Table([[left, right]], colWidths=[12.9*cm, 12.9*cm])
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("RIGHTPADDING", (0, 0), (0, 0), 8)]))
    story.append(row)
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Reproduce", KICK))
    story.append(Paragraph(
        "python rank.py --candidates ./data/candidates.jsonl --out "
        "./outputs/submission.csv", CODE))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Deterministic · CPU-only · offline · validated · sandbox demo via app.py. "
        "Full design rationale lives in the code (src/role_intent.py reads the JD "
        "line by line).", SMALL))

    Deck("docs/approach.pdf").build(story)
    print("wrote docs/approach.pdf")


if __name__ == "__main__":
    build()

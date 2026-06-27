"""
role_intent.py
==============
A *structured, auditable* encoding of what the Senior AI Engineer JD actually
*means* — not the words it contains.

The JD is unusually explicit: it lists what it wants, what it tolerates, and what
it actively rejects, and it openly warns that the dataset is seeded with traps
("the right answer is NOT find candidates whose skills section contains the most
AI keywords"). We translate every one of those statements into machine-checkable
intent here, so the scorer in `scoring.py` is a faithful, defensible reading of
the JD rather than a black box.

Nothing in this file is learned from labels (there are none); it is a hand-built
reading of the JD, which is exactly what a senior recruiter does on day one.
"""

# ---------------------------------------------------------------------------
# 1. WHAT THE ROLE IS ABOUT  (used for semantic / TF-IDF matching)
# ---------------------------------------------------------------------------
# A dense paragraph capturing the *substance* of the role. This is embedded into
# the same TF-IDF space as each candidate's career text so that a "Tier-5"
# candidate who built a recommender at a product company — but never wrote the
# word "RAG" — still scores well on meaning.
ROLE_QUERY = """
Senior AI engineer owning the intelligence layer of a talent platform: ranking,
retrieval and matching systems that decide what recruiters and candidates see.
Production experience with embeddings based retrieval, semantic search, vector
databases and hybrid search, dense and sparse retrieval, learning to rank,
recommendation systems, search relevance, information retrieval. Has shipped an
end to end ranking, search or recommendation system to real users at meaningful
scale at a product company. Strong Python and code quality. Designs evaluation
frameworks for ranking systems using NDCG, MRR, MAP, offline to online
correlation and A/B testing. LLM integration, fine tuning, re-ranking, knows
when to fine tune versus prompt. Scrappy product engineering attitude, ships
fast, iterates with real users, also has deep ML systems depth. Handled
embedding drift, index refresh and retrieval quality regression in production.
"""

# ---------------------------------------------------------------------------
# 2. CORE ROLE FAMILY  (title / career semantics)
# ---------------------------------------------------------------------------
# Titles that indicate the candidate actually works in the relevant discipline.
# Weight = how strongly the title alone signals fit (the JD's "Marketing Manager
# with all the AI keywords is NOT a fit" rule lives here).
STRONG_TITLES = {
    "ml engineer": 1.00, "machine learning engineer": 1.00,
    "applied scientist": 0.95, "applied ml": 0.95,
    "search engineer": 0.98, "relevance engineer": 0.98,
    "nlp engineer": 0.92, "ai engineer": 0.90,
    "research engineer": 0.78,            # ok IF production (see disqualifiers)
    "ai research engineer": 0.78,
    "data scientist": 0.72, "senior data scientist": 0.75,
    "recommendation": 0.95, "recsys": 0.95,
}
# Adjacent engineering titles — can be a great fit IF the career text shows
# retrieval/ranking/recsys work (the "plain-language Tier-5" case).
ADJACENT_TITLES = {
    "data engineer": 0.55, "analytics engineer": 0.50,
    "senior data engineer": 0.58, "backend engineer": 0.45,
    "software engineer": 0.40, "senior software engineer": 0.45,
    "platform engineer": 0.42, "mlops": 0.55, "ml platform": 0.62,
}
# Titles that are essentially never a fit for this specific role.
IRRELEVANT_TITLES = {
    "accountant", "hr manager", "civil engineer", "mechanical engineer",
    "graphic designer", "content writer", "sales executive",
    "marketing manager", "operations manager", "customer support",
    "project manager", "business analyst", "qa engineer",
    "frontend engineer", "mobile developer", ".net developer",
    "java developer", "full stack developer",
}

# ---------------------------------------------------------------------------
# 3. SKILL VOCABULARY  (evidence, not gospel — see trust multiplier in scoring)
# ---------------------------------------------------------------------------
# Grouped by how directly each skill maps to the JD's "absolutely need" list.
CORE_RETRIEVAL_SKILLS = {  # the heart of the role
    "embeddings", "semantic search", "vector search", "rag",
    "faiss", "pinecone", "weaviate", "qdrant", "milvus", "pgvector",
    "opensearch", "elasticsearch", "bm25", "hybrid search",
    "learning to rank", "information retrieval", "dense retrieval",
    "recommendation systems", "recsys", "search relevance",
    "sentence-transformers", "bge", "e5",
}
ML_DEPTH_SKILLS = {  # genuine ML systems depth
    "pytorch", "tensorflow", "hugging face transformers", "transformers",
    "fine-tuning llms", "lora", "qlora", "peft", "llms", "mlflow",
    "feature engineering", "scikit-learn", "ranking", "xgboost",
    "kubeflow", "bentoml", "weights & biases", "llamaindex", "langchain",
}
EVAL_SKILLS = {  # the JD makes evaluation a hard requirement
    "ndcg", "mrr", "map", "a/b testing", "ab testing", "evaluation",
    "offline evaluation", "experimentation",
}
# Skills the JD explicitly says are NOT the focus (CV / speech / robotics).
OFF_DOMAIN_SKILLS = {
    "image classification", "object detection", "yolo", "opencv",
    "computer vision", "cnn", "gans", "diffusion models",
    "speech recognition", "tts", "image segmentation",
    "robotics", "slam", "reinforcement learning",
}

# ---------------------------------------------------------------------------
# 4. CAREER-TEXT EVIDENCE PHRASES  (read the work, not the label)
# ---------------------------------------------------------------------------
# Phrases in job *descriptions* that prove real retrieval/ranking/recsys work.
POSITIVE_EVIDENCE = [
    "ranking", "retrieval", "recommendation", "recommender", "search relevance",
    "semantic search", "vector search", "embedding", "learning to rank",
    "search engine", "personalization", "relevance", "information retrieval",
    "matching", "nearest neighbor", "ann index", "a/b test", "ndcg",
    "shipped", "production", "at scale", "real users", "latency",
]
# Phrases that quietly *reduce* fit even inside an ML title (the dataset hides
# anti-signals in plain language, e.g. "lighter weight than ranking systems").
NEGATIVE_EVIDENCE = [
    "lighter weight than ranking", "lighter on the deep-learning",
    "primarily for an internal", "purely research", "research only",
    "no production", "proof of concept only", "mostly classification",
]

# ---------------------------------------------------------------------------
# 5. DISQUALIFIERS / DOWN-WEIGHTS  (the JD's "explicitly do NOT want")
# ---------------------------------------------------------------------------
CONSULTING_FIRMS = {
    "tcs", "tata consultancy", "infosys", "wipro", "accenture",
    "cognizant", "capgemini", "mindtree", "mphasis", "hcl", "tech mahindra",
    "ltimindtree", "l&t infotech", "hexaware",
}
# Geography the JD prefers (Pune/Noida + Tier-1 Indian cities open to relocation).
PREFERRED_LOCATIONS = {
    "pune", "noida", "delhi", "new delhi", "gurgaon", "gurugram",
    "hyderabad", "mumbai", "bangalore", "bengaluru", "chennai",
    "delhi ncr", "ncr",
}

# ---------------------------------------------------------------------------
# 6. EXPERIENCE BAND  (JD: "5-9, a range not a requirement")
# ---------------------------------------------------------------------------
EXP_IDEAL_LOW, EXP_IDEAL_HIGH = 6.0, 8.0   # "ideal candidate" 6-8 yrs
EXP_BAND_LOW, EXP_BAND_HIGH = 5.0, 9.0     # stated band
EXP_HARD_LOW, EXP_HARD_HIGH = 3.0, 13.0    # "will consider outside if strong"

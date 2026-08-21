import logging

log = logging.getLogger(__name__)

VISA_SIGNALS = [
    "open to relocation", "remote worldwide", "remote anywhere",
    "anywhere in the world", "international candidates",
    "visa sponsorship", "visa sponsor", "work authorization",
    "work permit", "willing to sponsor", "candidates from",
    "remote-first", "remote first", "distributed team",
    "global team", "eu blue card", "we sponsor",
    "relocation", "reloca",
]

SKILL_SIGNALS: dict[str, list[str]] = {
    "Vue.js": ["vue.js", "vuex", "nuxt"],
    "Python": ["python"],
    "FastAPI": ["fastapi"],
    "TypeScript": ["typescript"],
    "Docker": ["docker"],
    "PostgreSQL": ["postgresql", "postgres"],
    "React": ["react"],
    "Node.js": ["node.js", "nodejs"],
    "Django": ["django"],
    "Full Stack": ["full stack", "fullstack", "full-stack"],
    "JavaScript": ["javascript"],
    "REST API": ["rest api"],
    "Pydantic": ["pydantic"],
    "Async Python": ["async python"],
}

TARGET_REGIONS: dict[str, list[str]] = {
    "EU": ["europe", " eu ", "remote eu"],
    "BE": ["belgium", "brussels", "ghent", "antwerp"],
    "NL": ["netherlands", "amsterdam", "rotterdam"],
    "PL": ["poland", "warsaw", "krakow", "wroclaw"],
}

SKIP_SIGNALS = [
    "on-site only", "onsite only", "internship", "intern",
    "must be local", "must reside", "no relocation",
    "local candidates only", "staffing agency", "recruiting agency",
    "contract to hire agency", "fluent german required",
    "fluent french required", "fluent dutch required",
    "native speaker required", "0-1 years", "0-2 years",
]

VISA_WEIGHT = 0.40
SKILL_WEIGHT = 0.35
REGION_WEIGHT = 0.15


def extract_stack_match(text: str) -> list[str]:
    text_lower = text.lower()
    matched = []
    for canonical, kws in SKILL_SIGNALS.items():
        if any(kw in text_lower for kw in kws):
            matched.append(canonical)
    return matched


def extract_visa_signal(text: str) -> str | None:
    text_lower = text.lower()
    for signal in VISA_SIGNALS:
        if signal in text_lower:
            return signal
    return None


def infer_region(text_lower: str) -> tuple[str, str]:
    for region, keywords in TARGET_REGIONS.items():
        if any(kw in text_lower for kw in keywords):
            return ("EU" if region in ("BE", "NL", "PL") else region, region)

    if any(kw in text_lower for kw in ["worldwide", "anywhere", "remote"]):
        return ("REMOTE", "REMOTE")

    return ("UNKNOWN", "UNKNOWN")


def score_job(
    title: str,
    company: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> tuple[float, str | None, str, str, list[str]]:
    texts = " ".join(filter(None, [title, company or "", location or "", description or ""])).lower()

    for skip in SKIP_SIGNALS:
        if skip in texts:
            return (0.0, None, "UNKNOWN", "UNKNOWN", [])

    visa_signal = extract_visa_signal(texts)
    visa_hits = 1.0 if visa_signal else 0.0

    matched_skills = extract_stack_match(texts)
    skill_hits = min(len(matched_skills), 3)
    skill_score = skill_hits / 3.0

    region, country = infer_region(texts)
    region_hit = 1.0 if region in ("EU", "REMOTE") else 0.0

    score = round(
        visa_hits * VISA_WEIGHT + skill_score * SKILL_WEIGHT + region_hit * REGION_WEIGHT,
        4,
    )

    return (score, visa_signal, region, country, matched_skills)

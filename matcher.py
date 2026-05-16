"""
Scores jobs against candidate profile. Returns match score 0-100.
No LLM calls — pure keyword/rule scoring for speed.
"""
import json
import re
from pathlib import Path

PROFILE_PATH = Path(__file__).parent / "candidate_profile.json"
profile = json.loads(PROFILE_PATH.read_text())

# High relevance — direct Dillip expertise (4 pts each, cap 60)
HIGH_WEIGHT_KEYWORDS = [
    "substation", "eht", "400 kv", "220 kv", "132 kv", "33 kv",
    "erection", "commissioning", "o&m", "operation and maintenance",
    "transmission line", "transmission and distribution", "power transformer",
    "scada", "protection relay", "micom", "siprotec", "epc",
    "hv", "ehv", "extra high voltage", "high voltage",
    "switchyard", "gis", "ais", "vcb", "mcc", "rtcc", "plc", "vfd",
    "solar", "renewable energy", "biogas", "power plant",
    "electrical project", "site engineer", "site manager",
]

# Medium relevance (2 pts each, cap 30)
MED_WEIGHT_KEYWORDS = [
    "electrical engineer", "project manager", "project engineer",
    "11 kv", "switchgear", "transformer", "relay", "cable laying",
    "overhead line", "ohl", "steel plant", "psu", "infrastructure",
    "odisha", "bhubaneswar", "construction", "testing", "commissioning",
    "power sector", "energy", "utility", "grid", "distribution",
    "l&t", "larsen", "tata", "adani", "sterlite", "kalpataru",
    "abb", "siemens", "ge", "schneider", "hvdc", "facts",
]

EXCLUDE_KEYWORDS = [
    "software engineer", "web developer", "full stack", "data scientist",
    "bpo", "call centre", "telecalling", "marketing executive",
    "sales executive", "freshers only", "0-1 years", "0 to 1 year",
    "content writer", "graphic design", "ui/ux", "mobile app",
]

MIN_EXP_YEARS = int(profile.get("experience_years", 25)) - 15  # allow 10+ year roles


def _text(job: dict) -> str:
    return (
        (job.get("title") or "") + " " +
        (job.get("description") or "") + " " +
        (job.get("company") or "")
    ).lower()


def score_job(job: dict) -> int:
    text = _text(job)
    title = (job.get("title") or "").lower()

    # Hard exclude
    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            return 0

    # Reject clearly junior roles
    exp_match = re.search(r"(\d+)\s*[-–to]\s*(\d+)\s*years?", text)
    if exp_match:
        max_exp = int(exp_match.group(2))
        if max_exp < MIN_EXP_YEARS:
            return 0

    score = 0

    # High-weight matches (4 pts each, cap 64)
    hw_hits = sum(1 for kw in HIGH_WEIGHT_KEYWORDS if kw in text)
    score += min(hw_hits * 4, 64)

    # Med-weight matches (2 pts each, cap 30)
    mw_hits = sum(1 for kw in MED_WEIGHT_KEYWORDS if kw in text)
    score += min(mw_hits * 2, 30)

    # Title contains electrical/power/substation/transmission (strong signal)
    strong_title_words = [
        "electrical", "substation", "transmission", "power", "eht",
        "hv", "switchgear", "solar", "renewable", "o&m", "commissioning"
    ]
    title_hits = sum(1 for w in strong_title_words if w in title)
    score += min(title_hits * 6, 24)

    # Target role match bonus
    for role in profile["target_roles"]:
        words = [w for w in role.lower().split() if len(w) > 3]
        if any(w in title for w in words):
            score += 8
            break

    return min(score, 100)


def shortlist(jobs: list, min_score: int = 30) -> list:
    scored = []
    for job in jobs:
        s = score_job(job)
        if s >= min_score:
            job["match_score"] = s
            scored.append(job)
    return sorted(scored, key=lambda j: j["match_score"], reverse=True)

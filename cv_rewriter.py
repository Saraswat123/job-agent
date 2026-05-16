"""
CV tailoring helper — generates role-specific summary and bullet point emphasis.
Claude Code (subscription) writes the actual content; this file provides structure and output.
"""
import json
from pathlib import Path
from datetime import datetime

PROFILE = json.loads((Path(__file__).parent / "candidate_profile.json").read_text())
OUTBOX = Path(__file__).parent / "outbox"


def build_rewrite_prompt(job: dict) -> str:
    """
    Returns a prompt Claude Code should use to rewrite the CV summary.
    Claude Code reads this and writes the tailored text directly.
    """
    title = job.get("title", "")
    company = job.get("company", "")
    desc = (job.get("description") or "")[:1200]
    exp = PROFILE["experience"]

    return f"""Rewrite Dillip Kumar Das's CV summary and top 4 experience bullets for this role.

TARGET ROLE: {title}
COMPANY: {company}
JOB DESCRIPTION: {desc}

CANDIDATE PROFILE:
- 25+ years electrical/substation engineering
- Max voltage: 400 kV EHT substations
- Current: Project Manager, Nexband Optifibers (Biogas + Electrical, Jul 2024–present)
- Key past: SMEC India 400/220/132 kV Green Energy Corridor (KfW) | WAPCOS GoI 33/11 kV | Concast Steel 220 kV (7 yrs) | Srex Power 300 MW Solar PSS Siemens Gamesa
- Skills: Micom/SIPROTEC relays, SCADA/RTU, EPC, DPR, PESO/SPCB approvals, VFDs, MCC

RULES:
1. Write a 3-sentence professional summary tailored to THIS role (no generic phrases)
2. Pick 4 most relevant experience bullets from his background, reword to match JD keywords
3. Keep all technical terms exact (voltage levels, relay brands, project names)
4. Output format:
   SUMMARY: [3 sentences]
   BULLETS:
   - [bullet 1]
   - [bullet 2]
   - [bullet 3]
   - [bullet 4]"""


def save_tailored_cv(job_id: str, summary: str, bullets: list[str]) -> str:
    """Save tailored CV text to outbox for reference."""
    OUTBOX.mkdir(exist_ok=True)
    out = {
        "job_id": job_id,
        "generated_at": datetime.now().isoformat(),
        "tailored_summary": summary,
        "tailored_bullets": bullets,
    }
    path = OUTBOX / f"cv_tailored_{job_id}.json"
    path.write_text(json.dumps(out, indent=2))
    return str(path)


def get_email_body_template(job: dict, tailored_summary: str = "", tailored_bullets: list = None) -> str:
    """
    Build email body using tailored content.
    If tailored content not provided, uses profile defaults.
    """
    p = PROFILE["personal"]
    title = job.get("title", "")
    company = job.get("company", "")
    summary = tailored_summary or PROFILE["summary"][:300]
    bullets = tailored_bullets or [
        "Led end-to-end 400/220/132 kV substation construction (Green Energy Corridor, KfW-funded, MPPTCL client)",
        "7 years O&M at 220/33/6.6 kV integrated steel plant (Concast Steel & Power, Jharsuguda)",
        "Commissioned 300 MW Solar PSS (33/220 kV), Thar Surya-1, Bikaner — Siemens Gamesa project",
        "Project Manager: 6 TPD Biogas Plant with PESO, SPCB, Fire Safety regulatory clearances",
    ]

    bullet_text = "\n".join(f"• {b}" for b in bullets[:4])

    return f"""Dear Hiring Manager,

I am applying for the position of {title} at {company}. {summary}

Key highlights relevant to this role:
{bullet_text}

I am based in Bhubaneswar, Odisha and open to PAN India relocation. My CV is attached for your review. I am available for an interview at short notice.

Regards,
Dillip Kumar Das
+91 9937146272 | {p['email']}"""

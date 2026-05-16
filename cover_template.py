"""
Cover letter builder — pure data helper, no API calls.
Claude Code (subscription) writes the actual cover letter text.
This module provides structure, templates, and subject lines.
"""
import json
from pathlib import Path

PROFILE = json.loads((Path(__file__).parent / "candidate_profile.json").read_text())
p = PROFILE["personal"]


def generate_subject(job_title: str) -> str:
    return f"Application for {job_title} – Dillip Kumar Das"


def build_cover_prompt(job: dict) -> str:
    """
    Returns a prompt for Claude Code to generate a tailored cover letter.
    Claude Code reads this and writes the email body inline.
    """
    title = job.get("title", "")
    company = job.get("company", "")
    desc = (job.get("description") or "")[:1200]

    return f"""Write a job application email body for Dillip Kumar Das.

ROLE: {title}
COMPANY: {company}
JOB DESCRIPTION: {desc}

CANDIDATE FACTS:
- 25+ years electrical infrastructure: substations up to 400 kV, transmission lines 220 kV
- Current: Project Manager – Biogas & Electrical Infra, Nexband Optifibers (Jul 2024–present)
- Notable: 400/220/132 kV Green Energy Corridor KfW India (SMEC/MPPTCL) | 300 MW Solar PSS Siemens Gamesa | WAPCOS GoI 33/11 kV | Concast Steel 220 kV 7 years
- Skills: Micom/SIPROTEC relays, SCADA/RTU, EPC contracts, DPR, PESO/SPCB approvals, VFDs, MCC panels
- Location: Bhubaneswar, open PAN India relocation
- Contact: +91 9937146272 | dillip.das4@gmail.com

EMAIL RULES:
- Under 200 words
- 3 paragraphs: hook with most relevant experience → 2-3 specific achievements from JD → CTA
- Reference specific voltage levels / technologies matching JD
- End exactly with: "My CV is attached. Available for interview at short notice."
- No subject line. No "Dear [name]" header. Output email body only."""


def default_email_body(job: dict) -> str:
    """
    Fallback template when Claude Code is not orchestrating.
    Used only in standalone python daily_agent.py runs.
    """
    title = job.get("title", "")
    company = job.get("company", "")

    return f"""Dear Hiring Manager,

I am writing to apply for the position of {title} at {company}. With 25+ years of hands-on experience in erection, testing, commissioning, and O&M of EHT substations up to 400 kV and transmission lines up to 220 kV, I bring deep technical expertise and proven project delivery capability.

Key experience relevant to this role: supervised 400/220/132 kV substation construction under Green Energy Corridor (KfW-funded, MPPTCL), commissioned 300 MW Solar PSS (Siemens Gamesa), 7 years O&M at 220 kV integrated steel plant, and currently managing a full-cycle Biogas Plant including PESO/SPCB regulatory clearances and EPC coordination.

I am based in Bhubaneswar and open to PAN India relocation. My CV is attached. Available for interview at short notice.

Regards,
Dillip Kumar Das
+91 9937146272 | {p['email']}"""

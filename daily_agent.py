"""
Modular CLI orchestrator — Claude Code calls each phase separately.
Usage:
  python daily_agent.py search              → fetch jobs, save raw_jobs.json
  python daily_agent.py match               → score + shortlist, save shortlist_DATE.json
  python daily_agent.py emails <role>       → find HR emails from LinkedIn posts + web
  python daily_agent.py send <job_id> <to> "<cover_letter>"  → send email + mark applied
  python daily_agent.py apply <job_id>      → browser Easy Apply
  python daily_agent.py followup            → send follow-up emails (7-day)
  python daily_agent.py status              → print stats
  python daily_agent.py run                 → full autonomous pipeline (standalone mode)
"""
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).parent
OUTBOX = BASE / "outbox"
LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)
OUTBOX.mkdir(exist_ok=True)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "agent.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)
TODAY = datetime.now().strftime("%Y-%m-%d")
MAX_APPLY = int(os.getenv("MAX_APPLY_PER_DAY", "15"))
MIN_SCORE = int(os.getenv("MIN_MATCH_SCORE", "60"))
COOLDOWN = int(os.getenv("REAPPLY_COOLDOWN_DAYS", "30"))


# ── Phase: Search ────────────────────────────────────────────────────────────

def cmd_search():
    from job_search import search_all_jobs, fetch_description
    log.info("Phase: Search")
    jobs = search_all_jobs()
    log.info(f"Raw jobs found: {len(jobs)}")

    print("Fetching descriptions...")
    for i, job in enumerate(jobs):
        if not job.get("description"):
            job["description"] = fetch_description(job)
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(jobs)} fetched")

    out = OUTBOX / "raw_jobs.json"
    out.write_text(json.dumps(jobs, indent=2))
    print(f"\nSaved {len(jobs)} jobs → {out}")
    log.info(f"Search complete: {len(jobs)} jobs saved")


# ── Phase: Match ─────────────────────────────────────────────────────────────

def cmd_match():
    from matcher import shortlist
    raw_path = OUTBOX / "raw_jobs.json"
    if not raw_path.exists():
        print("ERROR: raw_jobs.json not found. Run search first.")
        sys.exit(1)
    jobs = json.loads(raw_path.read_text())
    ranked = shortlist(jobs, min_score=MIN_SCORE)
    out = OUTBOX / f"shortlist_{TODAY}.json"
    out.write_text(json.dumps(ranked, indent=2))
    print(f"\nShortlisted {len(ranked)} jobs (score ≥ {MIN_SCORE}) → {out}")
    for j in ranked[:10]:
        print(f"  [{j['match_score']:3d}] {j['title'][:40]} @ {j['company'][:25]} ({j['source']})")
    log.info(f"Match complete: {len(ranked)} shortlisted")


# ── Phase: Find emails ───────────────────────────────────────────────────────

def cmd_emails(role: str):
    from job_search import scrape_linkedin_posts_for_emails
    from web_search import search_hr_email, search_linkedin_posts_for_emails
    print(f"Searching HR emails for role: {role}")

    # LinkedIn post scrape
    li_emails = scrape_linkedin_posts_for_emails(role)
    # Web search
    web_emails_raw = search_linkedin_posts_for_emails(role)

    all_emails = list(dict.fromkeys(li_emails + web_emails_raw))
    print(f"Found {len(all_emails)} emails:")
    for e in all_emails:
        print(f"  {e}")
    return all_emails


# ── Phase: Send email ────────────────────────────────────────────────────────

def cmd_send(job_id: str, to_email: str, cover_letter: str):
    from tracker import is_duplicate, mark_applied, upsert_job
    from gmail_sender import send_application_email

    shortlist_path = OUTBOX / f"shortlist_{TODAY}.json"
    if not shortlist_path.exists():
        # Try any shortlist
        files = sorted(OUTBOX.glob("shortlist_*.json"), reverse=True)
        if not files:
            print("ERROR: No shortlist found. Run match first.")
            sys.exit(1)
        shortlist_path = files[0]

    jobs = json.loads(shortlist_path.read_text())
    job = next((j for j in jobs if j["id"] == job_id), None)

    if not job:
        print(f"ERROR: job_id {job_id} not in shortlist")
        sys.exit(1)

    if is_duplicate(job_id, COOLDOWN):
        print(f"SKIP: Already applied to {job['company']} within {COOLDOWN} days")
        return

    subject = f"Application for {job['title']} – Dillip Kumar Das"

    upsert_job({
        "id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "location": job.get("location", ""),
        "source": job["source"],
        "url": job["url"],
        "match_score": job.get("match_score", 0),
        "status": "found",
    })

    ok = send_application_email(to=to_email, subject=subject, cover_letter=cover_letter)

    if ok:
        mark_applied(job_id, cover_letter)
        print(f"✓ Sent: {job['title']} @ {job['company']} → {to_email}")
        log.info(f"Applied: {job_id} | {job['title']} @ {job['company']} → {to_email}")
    else:
        print(f"✗ Failed to send: {job['title']} @ {job['company']}")
        log.error(f"Send failed: {job_id}")


# ── Phase: Browser apply ──────────────────────────────────────────────────────

def cmd_apply(job_id: str):
    from apply_playwright import apply_sync
    from tracker import mark_applied
    from cover_template import default_email_body

    shortlist_path = sorted(OUTBOX.glob("shortlist_*.json"), reverse=True)
    if not shortlist_path:
        print("No shortlist. Run match first.")
        return

    jobs = json.loads(shortlist_path[0].read_text())
    job = next((j for j in jobs if j["id"] == job_id), None)
    if not job:
        print(f"job_id {job_id} not found")
        return

    cover = default_email_body(job)
    ok = apply_sync(job, cover)
    if ok:
        mark_applied(job_id, cover)
        print(f"✓ Browser applied: {job['title']} @ {job['company']}")
        log.info(f"Browser applied: {job_id}")
    else:
        print(f"✗ Browser apply failed: {job['title']}")


# ── Phase: Follow-up ──────────────────────────────────────────────────────────

def cmd_followup():
    from tracker import get_pending_followups, mark_followup_sent
    from gmail_sender import send_followup_email

    pending = get_pending_followups()
    print(f"Pending follow-ups: {len(pending)}")
    sent = 0
    for fu in pending:
        body = (
            f"Dear Hiring Team,\n\n"
            f"I applied for the {fu['title']} position at {fu['company']} one week ago "
            f"and wanted to follow up on my application. With 25+ years in EHT substations "
            f"and transmission line projects, I remain very interested in this opportunity.\n\n"
            f"Please let me know if you need any additional information. "
            f"I am available for an interview at your convenience.\n\n"
            f"Regards,\nDillip Kumar Das\n+91 9937146272 | dillip.das4@gmail.com"
        )
        subject = f"Follow-up: {fu['title']} Application – Dillip Kumar Das"
        ok = send_followup_email(
            to=f"hr@{fu['company'].lower().replace(' ', '')}.com",
            subject=subject,
            body=body,
        )
        if ok:
            mark_followup_sent(fu["id"])
            sent += 1
            print(f"  ✓ Follow-up sent: {fu['title']} @ {fu['company']}")
    print(f"Follow-ups sent: {sent}")


# ── Phase: Status ─────────────────────────────────────────────────────────────

def cmd_status():
    from tracker import daily_stats
    s = daily_stats()
    print(f"""
══ Agent Status {TODAY} ══
  Applied today : {s['applied_today']}
  Total applied : {s['total_applied']}
  Total tracked : {s['total_found']}
  Shortlist     : outbox/shortlist_{TODAY}.json
  Log           : logs/agent.log
""")


# ── Full autonomous run (standalone, no Claude Code) ─────────────────────────

def cmd_run():
    """
    Full pipeline without Claude Code.
    Uses default_email_body template (no AI tailoring).
    For AI-tailored emails, use Claude Code with CLAUDE.md workflow instead.
    """
    from tracker import upsert_job, is_duplicate, mark_applied
    from gmail_sender import send_application_email
    from email_extractor import find_company_hr_email, extract_from_text
    from cover_template import default_email_body
    from apply_playwright import apply_sync
    from matcher import shortlist
    from job_search import search_all_jobs, fetch_description

    print("═" * 50)
    print(f"Job Agent — {TODAY}")
    print("═" * 50)

    print("\n► Searching jobs...")
    jobs = search_all_jobs()
    print(f"  Found {len(jobs)} raw jobs")

    print("\n► Fetching descriptions...")
    for job in jobs:
        if not job.get("description"):
            job["description"] = fetch_description(job)

    print("\n► Shortlisting...")
    ranked = shortlist(jobs, min_score=MIN_SCORE)
    (OUTBOX / f"shortlist_{TODAY}.json").write_text(json.dumps(ranked, indent=2))
    print(f"  Shortlisted: {len(ranked)}")

    applied = 0
    print(f"\n► Applying (max {MAX_APPLY}/day)...")
    for job in ranked:
        if applied >= MAX_APPLY:
            break
        if is_duplicate(job["id"], COOLDOWN):
            continue

        upsert_job({
            "id": job["id"], "title": job["title"], "company": job["company"],
            "location": job.get("location", ""), "source": job["source"],
            "url": job["url"], "match_score": job.get("match_score", 0), "status": "found",
        })

        # Find HR email
        hr_email = extract_from_text(job.get("description", ""))
        hr_email = hr_email[0] if hr_email else find_company_hr_email(job["company"], job["title"])

        cover = default_email_body(job)
        subject = f"Application for {job['title']} – Dillip Kumar Das"

        sent = False
        if hr_email:
            sent = send_application_email(to=hr_email, subject=subject, cover_letter=cover)
            print(f"  {'✓' if sent else '✗'} Email → {hr_email}: {job['title']} @ {job['company']}")

        # Browser apply for LinkedIn/Naukri
        browser_ok = False
        if job["source"] in ("linkedin", "naukri"):
            browser_ok = apply_sync(job, cover)
            print(f"  {'✓' if browser_ok else '✗'} Browser: {job['title']} @ {job['company']}")

        if sent or browser_ok:
            mark_applied(job["id"], cover)
            applied += 1
            log.info(f"Applied: {job['id']} | {job['title']} @ {job['company']}")

    cmd_status()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "status"

    if cmd == "search":
        cmd_search()
    elif cmd == "match":
        cmd_match()
    elif cmd == "emails":
        role = args[1] if len(args) > 1 else "Electrical Engineer Substation"
        cmd_emails(role)
    elif cmd == "send":
        if len(args) < 4:
            print("Usage: python daily_agent.py send <job_id> <to_email> '<cover_letter>'")
            sys.exit(1)
        cmd_send(args[1], args[2], args[3])
    elif cmd == "apply":
        if len(args) < 2:
            print("Usage: python daily_agent.py apply <job_id>")
            sys.exit(1)
        cmd_apply(args[1])
    elif cmd == "followup":
        cmd_followup()
    elif cmd == "status":
        cmd_status()
    elif cmd == "run":
        cmd_run()
    else:
        print(__doc__)

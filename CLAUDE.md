# Job Application Agent — Claude Code Instructions

## Who you are
You are the AI brain of a job application agent for Dillip Kumar Das.
Read `candidate_profile.json` for his full background.
CV is at `assets/Dillip_Kumar_Das_CV.pdf`.
You use Claude Code subscription — no external API calls needed. You write cover letters yourself.

## Candidate quick facts
- Name: Dillip Kumar Das | Email: dillip.das4@gmail.com | Phone: +91 9937146272
- 25+ years EHT substations (up to 400 kV), transmission lines (220 kV), O&M, renewables
- Location: Bhubaneswar, Odisha | Open to PAN India relocation
- Target: Substation Engineer, Project Manager Electrical, O&M Engineer, Transmission Line Engineer

## Daily workflow — run when user says "run job agent" or "apply today"

### Step 1: Search
```bash
cd /Users/aitsgroup/Downloads/Personal_Documents/Dillip/job-agent
source .venv/bin/activate
python daily_agent.py search
```

### Step 2: Match + shortlist
```bash
python daily_agent.py match
```
Read `outbox/shortlist_YYYY-MM-DD.json`. Review top 20 jobs.

### Step 3: Find HR emails + apply (for EACH job in shortlist)

For each job:
1. **Extract email from description** — look in `description` field for any email address
2. **If no email** — run web search:
   ```bash
   python daily_agent.py emails "Substation Engineer"
   ```
3. **Write tailored cover letter** (YOU write this — see email rules below)
4. **Send email**:
   ```bash
   python daily_agent.py send <job_id> <hr_email> "<cover_letter_text>"
   ```
5. **Browser apply** (LinkedIn/Naukri Easy Apply — auto-submits):
   ```bash
   python daily_agent.py apply <job_id>
   ```

### Step 4: Follow-ups (7-day)
```bash
python daily_agent.py followup
```

### Step 5: Summary
```bash
python daily_agent.py status
```

---

## Email rules (YOU write these)
- Under 200 words
- 3 paragraphs: hook with most relevant experience → 2-3 specific achievements matching JD → CTA
- Reference SPECIFIC voltage levels, relay brands, project names from the JD
- End exactly: "My CV is attached. Available for interview at short notice."
- No subject line in body. No "Dear [Name]" header.
- Subject format: `Application for [JOB TITLE] – Dillip Kumar Das`

## CV tailoring per job
When JD emphasizes specific tech (e.g. 400 kV, SIPROTEC, solar, biogas):
- Reorder which 3-4 experience bullets you include
- Match JD keywords exactly
- Strengthen the hook sentence with the most relevant project

## LinkedIn post scraping for emails
Search LinkedIn posts where companies post hiring requirements with email addresses:
```bash
python daily_agent.py emails "Substation Project Engineer Odisha"
```
Also manually use Playwright MCP to:
1. Go to linkedin.com/search/results/content/?keywords=substation+engineer+hiring+email+cv
2. Read posts — extract any email addresses mentioned
3. Use those emails for direct application

## Email send rules
- ALWAYS send (not draft) — `EMAIL_MODE=send` in .env
- Every email must have CV attached (`assets/Dillip_Kumar_Das_CV.pdf`)
- If HR email unknown, skip email but still do browser apply

## What NOT to do
- Do not apply to same company within 30 days (tracker handles this)
- Do not apply to roles asking <10 years experience
- Do not apply to software/IT/BPO/sales roles

## Key files
| File | Purpose |
|---|---|
| `daily_agent.py search` | Fetch jobs from LinkedIn/Naukri/Indeed |
| `daily_agent.py match` | Score + shortlist |
| `daily_agent.py send` | Send email via Gmail API |
| `daily_agent.py apply` | Browser auto-apply |
| `email_extractor.py` | Extract HR emails from text/web |
| `tracker.py` | Prevent duplicate applications |
| `outbox/shortlist_DATE.json` | Today's job matches |
| `outbox/jobs.db` | All applications history |
| `logs/agent.log` | Full run log |

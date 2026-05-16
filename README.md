# Job Agent — Automated Job Application Bot

> **Set it and forget it.** Searches 200+ jobs daily, scores matches, extracts HR emails, writes tailored cover letters with AI, and sends applications with your CV — fully automated at 8 AM every morning.

**46 applications sent on Day 1.**

---

## How It Works

```
08:00 AM (daily, automatic)
│
├── Search LinkedIn + Naukri + DuckDuckGo
│       → 200+ jobs fetched across all sources
│
├── Score & Shortlist  (matcher.py — keyword scorer, 0–100)
│       → Top 30–50 relevant roles selected
│
├── Extract HR Emails  (email_extractor.py)
│       → Regex scan of job description
│       → DuckDuckGo web search fallback
│       → Company website crawl fallback
│
├── Write Tailored Cover Letter  (Claude Code AI via CLAUDE.md)
│       → References specific tech from each JD
│       → Mentions voltage levels, relay brands, project types
│       → Under 200 words, 3 paragraphs
│
├── Send Email via Gmail API  (gmail_sender.py)
│       → CV auto-attached every time
│       → Logged to SQLite tracker
│
├── Browser Auto-Apply  (apply_playwright.py)
│       → LinkedIn Easy Apply — multi-step form fill + submit
│       → Naukri Apply — form fill + submit
│       → Persistent Chromium profile — log in once, runs forever
│
└── Schedule 7-day Follow-up  (tracker.py)
        → Auto-sends follow-up email after 7 days
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.9+ |
| **Browser Automation** | [Playwright](https://playwright.dev/python/) — async, persistent Chromium profile |
| **Job Search** | LinkedIn public scraping · Naukri JSON API · DuckDuckGo HTML |
| **Email** | Gmail API (OAuth 2.0) via `google-api-python-client` |
| **AI Cover Letters** | [Claude Code](https://claude.ai/code) (Anthropic subscription — no API key needed) |
| **Matching Engine** | Custom keyword scorer — no LLM, instant, configurable weights |
| **Storage** | SQLite (`tracker.py`) — dedup, cooldown, follow-up scheduling |
| **Scheduling** | macOS LaunchAgent (8 AM daily) · `schedule` library fallback |
| **HTTP / Scraping** | `requests` · `BeautifulSoup4` · `lxml` · `fake-useragent` · `tenacity` |
| **Config** | `.env` via `python-dotenv` |

---

## Project Structure

```
job-agent/
│
├── daily_agent.py          # Main CLI — search / match / send / apply / followup / run
├── job_search.py           # LinkedIn scraper + Naukri API + DuckDuckGo fallback
├── matcher.py              # Keyword scorer (0-100) — no LLM, instant
├── email_extractor.py      # HR email extraction: regex + DuckDuckGo + website crawl
├── web_search.py           # DuckDuckGo / web search utilities
├── gmail_sender.py         # Gmail API — sends directly (not drafts), auto-attaches CV
├── gmail_setup.py          # One-time OAuth flow → generates token.json
├── apply_playwright.py     # Playwright browser auto-apply: LinkedIn Easy Apply + Naukri
├── linkedin_login.py       # Extract LinkedIn cookies from Comet browser (macOS Keychain AES)
├── cover_template.py       # Cover letter structure + prompt builder for Claude Code
├── cv_rewriter.py          # CV summary tailoring prompt generator
├── tracker.py              # SQLite — dedup, applied status, follow-up scheduling
├── schedule_agent.py       # Python schedule loop (alternative to LaunchAgent)
├── send_batch.py           # One-off batch sender for existing shortlists
│
├── candidate_profile.json  # YOUR profile — edit with your details
├── CLAUDE.md               # Claude Code AI workflow instructions
├── .env                    # Secrets — never commit (see .env.example)
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
│
├── assets/
│   └── your_cv.pdf         # Your CV — auto-attached to every application email
│
├── outbox/
│   ├── jobs.db             # SQLite — all application history
│   ├── raw_jobs.json       # Raw search results cache
│   └── shortlist_YYYY-MM-DD.json   # Daily shortlisted jobs
│
└── logs/
    └── agent.log           # Full run log
```

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/job-agent.git
cd job-agent

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Your Profile

Edit `candidate_profile.json`:

```json
{
  "personal": {
    "name": "Your Full Name",
    "email": "you@gmail.com",
    "phone": "+91 9999999999",
    "location": "Your City, India"
  },
  "experience_years": 10,
  "summary": "Your 2-line professional summary...",
  "target_roles": [
    "Electrical Engineer",
    "Project Manager",
    "Substation Engineer"
  ],
  "skills": { ... }
}
```

### 3. Set Environment Variables

```bash
cp .env.example .env
nano .env
```

Key variables:

```env
GMAIL_SENDER_ADDRESS=you@gmail.com

LINKEDIN_EMAIL=you@gmail.com
LINKEDIN_PASSWORD=your_password

NAUKRI_EMAIL=you@gmail.com
NAUKRI_PASSWORD=your_password

TARGET_ROLES=Electrical Engineer,Project Manager,Substation Engineer
TARGET_LOCATIONS=India

MIN_MATCH_SCORE=30
MAX_APPLY_PER_DAY=15
EMAIL_MODE=send          # send = auto-send | draft = save to Gmail Drafts
```

### 4. Gmail OAuth Setup (one-time)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. New project → Enable **Gmail API**
3. Credentials → OAuth 2.0 Client ID → **Desktop App** → Download as `credentials.json`
4. Place `credentials.json` in the project root
5. Run:

```bash
python gmail_setup.py
```

Browser opens → sign in → authorize → `token.json` created. Done.

### 5. Add Your CV

```bash
cp /path/to/your_cv.pdf assets/your_cv.pdf
```

Update `CV_PATH` in `gmail_sender.py` and `apply_playwright.py` to match your filename.

### 6. LinkedIn Browser Session (one-time)

```bash
python apply_playwright.py
```

Chromium opens → log into LinkedIn manually → session saved to `browser_profile/`.  
All future runs reuse the saved session — no re-login needed.

### 7. Enable Daily Automation

**macOS (LaunchAgent):**

```bash
# Edit paths in the plist file first
cp com.jobagent.example.plist ~/Library/LaunchAgents/com.jobagent.plist
launchctl load ~/Library/LaunchAgents/com.jobagent.plist
```

**Linux/Windows (cron):**

```bash
# crontab -e
0 8 * * * cd /path/to/job-agent && .venv/bin/python3 daily_agent.py run >> logs/cron.log 2>&1
```

**Python scheduler (any OS):**

```bash
python schedule_agent.py &
```

---

## CLI Usage

```bash
source .venv/bin/activate

# Full pipeline — search → match → email → browser apply
python daily_agent.py run

# Step by step
python daily_agent.py search              # Fetch jobs from all sources
python daily_agent.py match               # Score and shortlist
python daily_agent.py emails "Role Name"  # Find HR emails for a role
python daily_agent.py send <job_id> <hr@company.com> "cover letter text"
python daily_agent.py apply <job_id>      # Browser auto-apply
python daily_agent.py followup            # Send 7-day follow-ups
python daily_agent.py status              # Summary stats
```

---

## Matching Algorithm

`matcher.py` scores jobs 0–100 using weighted keywords — no LLM, no API calls, instant:

| Signal | Points | Cap |
|---|---|---|
| High-relevance skills (domain-specific: "substation", "400 kV", "scada", "epc") | 4 pts each | 64 |
| Medium-relevance (general: "electrical engineer", "transformer", target companies) | 2 pts each | 30 |
| Title keywords ("electrical", "transmission", "power" in job title) | 6 pts each | 24 |
| Target role exact match bonus | +8 pts | — |

Jobs below `MIN_MATCH_SCORE` are dropped. Keywords in `EXCLUDE_KEYWORDS` (software, BPO, freshers) → score 0.

**Customise for your domain:** Edit `HIGH_WEIGHT_KEYWORDS` and `MED_WEIGHT_KEYWORDS` in `matcher.py`.

---

## AI Cover Letters

Two modes — automatic fallback:

**Mode 1: Claude Code (AI — best results)**  
Run `python daily_agent.py run` from within Claude Code terminal.  
Claude reads `CLAUDE.md` instructions + each job description → writes a 3-paragraph letter referencing specific technologies, project names, and voltage levels from the JD.  
No API key needed — uses your Claude Code subscription.

**Mode 2: Template (standalone fallback)**  
`cover_template.py` builds a solid generic letter from `candidate_profile.json`.  
Used when running without Claude Code.

---

## Email Extraction

`email_extractor.py` tries three strategies per job:

1. **Regex scan** — extract any email from the job description text
2. **DuckDuckGo search** — `"Company Name" HR email careers jobs`
3. **Website crawl** — `company.com/careers`, `/jobs`, `/contact`

Prioritises HR-pattern emails (`hr@`, `careers@`, `recruit@`, `talent@`, `people@`).

---

## Deduplication & Follow-ups

`tracker.py` (SQLite `outbox/jobs.db`):

- Skips re-application to same job within `REAPPLY_COOLDOWN_DAYS` (default: 30 days)
- Schedules follow-up email 7 days after each application
- Run `python daily_agent.py followup` to dispatch due follow-ups

---

## Customise for Your Domain

### Different industry

Update `matcher.py`:

```python
HIGH_WEIGHT_KEYWORDS = [
    "kubernetes", "microservices", "aws", "go", "python",
    "distributed systems", "kafka", "postgres",
    # your tech stack
]
MED_WEIGHT_KEYWORDS = [
    "backend", "api", "cloud", "devops", "ci/cd",
    # broader terms
]
EXCLUDE_KEYWORDS = [
    "freshers only", "0-1 years", "sales executive",
    # what to reject
]
```

### Different job sources

Edit `job_search.py` — add scrapers for other job boards (Indeed, Glassdoor, etc.).

### Different cover letter style

Edit `CLAUDE.md` — Claude reads this every run as its instructions.

---

## Requirements

```
Python 3.9+
Playwright Chromium browser
Gmail API credentials (Google Cloud Console — free tier)
LinkedIn account (for scraping + Easy Apply)
Claude Code subscription (for AI cover letters — optional, template fallback available)
```

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `GMAIL_SENDER_ADDRESS` | — | Gmail address to send from |
| `LINKEDIN_EMAIL` | — | LinkedIn login email |
| `LINKEDIN_PASSWORD` | — | LinkedIn password |
| `NAUKRI_EMAIL` | — | Naukri login |
| `NAUKRI_PASSWORD` | — | Naukri password |
| `TARGET_ROLES` | — | Comma-separated job titles to search |
| `TARGET_LOCATIONS` | India | Search locations |
| `MIN_MATCH_SCORE` | 30 | Minimum score to apply (0–100) |
| `MAX_APPLY_PER_DAY` | 15 | Daily application cap |
| `REAPPLY_COOLDOWN_DAYS` | 30 | Days before re-applying to same company |
| `EMAIL_MODE` | send | `send` = auto-send · `draft` = save to Gmail Drafts |
| `AGENT_RUN_TIME` | 08:00 | Daily schedule time (24h format) |
| `LOG_LEVEL` | INFO | Logging verbosity |

---

## Security

- `.env`, `token.json`, `credentials.json`, `linkedin_session.json` — all in `.gitignore`, never committed
- Gmail OAuth token auto-refreshes silently after first setup
- LinkedIn session stored in `browser_profile/` (local Chromium profile) — not committed
- Consider using a dedicated Gmail address and LinkedIn app password for added isolation

---

## License

MIT — fork, adapt, use for your own job search.

---

## Contributing

PRs welcome. Ideas:
- Indeed / Glassdoor / Shine scrapers
- Telegram / WhatsApp notification on application sent
- LLM-based matcher (replace keyword scorer)
- Dashboard (FastAPI + React) to view application pipeline
- Resume PDF rewriting with `reportlab`

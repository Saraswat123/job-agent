"""
Scrapes LinkedIn, Naukri, Indeed for matching jobs.
Returns list of job dicts: {id, title, company, location, description, url, source}
"""
import os
import re
import hashlib
import time
import random
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

ua = UserAgent()

TARGET_ROLES = [r.strip() for r in os.getenv(
    "TARGET_ROLES",
    "Electrical Engineer Substation,Substation Project Engineer,EHT Engineer"
).split(",")]

TARGET_LOCATIONS = [l.strip() for l in os.getenv(
    "TARGET_LOCATIONS", "Odisha,India"
).split(",")]


def _headers():
    return {
        "User-Agent": ua.random,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def _job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _sleep():
    time.sleep(random.uniform(2.5, 5.5))


# ── LinkedIn ────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def _search_linkedin(role: str, location: str) -> list[dict]:
    query = role.replace(" ", "%20")
    loc = location.replace(" ", "%20")
    # No time filter — broader results
    url = (
        f"https://www.linkedin.com/jobs/search/?keywords={query}"
        f"&location={loc}&sortBy=DD&position=1&pageNum=0"
    )
    headers = _headers()
    headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    jobs = []
    # Try multiple card selectors (LinkedIn changes HTML frequently)
    cards = (
        soup.select("div.base-card") or
        soup.select("li.jobs-search-results__list-item") or
        soup.select("div.job-search-card")
    )
    for card in cards[:25]:
        try:
            title_el = (
                card.select_one("h3.base-search-card__title") or
                card.select_one("h3.job-search-card__title") or
                card.select_one("a.job-search-card__title-link")
            )
            company_el = (
                card.select_one("h4.base-search-card__subtitle") or
                card.select_one("a.job-search-card__subtitle-link") or
                card.select_one("span.job-search-card__company-name")
            )
            link_el = (
                card.select_one("a.base-card__full-link") or
                card.select_one("a.job-search-card__title-link")
            )
            loc_el = card.select_one("span.job-search-card__location")
            if not (title_el and link_el):
                continue
            job_url = link_el["href"].split("?")[0]
            jobs.append({
                "id": _job_id(job_url),
                "title": title_el.text.strip(),
                "company": company_el.text.strip() if company_el else "Unknown",
                "location": loc_el.text.strip() if loc_el else location,
                "url": job_url,
                "source": "linkedin",
                "description": "",
                "status": "found",
            })
        except Exception:
            continue
    return jobs


# ── Naukri ──────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def _search_naukri(role: str, location: str) -> list[dict]:
    # Naukri API endpoint (JSON) — more reliable than HTML scraping
    params = {
        "noOfResults": 20,
        "urlType": "search_by_keyword",
        "searchType": "adv",
        "keyword": role,
        "location": location,
        "jobAge": 7,
        "experience": 10,
        "src": "jobsearchDesk",
        "latLong": "",
    }
    headers = _headers()
    headers.update({
        "Accept": "application/json",
        "Referer": "https://www.naukri.com/",
        "appid": "109",
        "systemid": "109",
    })
    try:
        resp = requests.get(
            "https://www.naukri.com/jobapi/v3/search",
            params=params, headers=headers, timeout=15
        )
        data = resp.json()
        jobs = []
        for item in (data.get("jobDetails") or [])[:20]:
            job_url = item.get("jdURL", "")
            if not job_url:
                continue
            if not job_url.startswith("http"):
                job_url = "https://www.naukri.com" + job_url
            jobs.append({
                "id": _job_id(job_url),
                "title": item.get("title", role),
                "company": item.get("companyName", "Unknown"),
                "location": ", ".join(item.get("placeholders", [{}])[0].get("label", location).split(",")[:2]) if item.get("placeholders") else location,
                "url": job_url,
                "source": "naukri",
                "description": item.get("jobDescription", ""),
                "status": "found",
            })
        return jobs
    except Exception:
        # Fallback: HTML scrape with updated selectors
        role_slug = role.lower().replace(" ", "-").replace("&", "and")
        loc_slug = location.lower().replace(" ", "-")
        url = f"https://www.naukri.com/{role_slug}-jobs-in-{loc_slug}"
        resp = requests.get(url, headers=_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        jobs = []
        for card in soup.select("article.jobTuple, div.srp-jobtuple-wrapper")[:20]:
            try:
                title_el = card.select_one("a.title, a.jobTitle")
                company_el = card.select_one("a.subTitle, span.companyInfo a")
                loc_el = card.select_one("li.location span, span.locWdth")
                if not title_el:
                    continue
                job_url = title_el.get("href", "")
                if not job_url:
                    continue
                jobs.append({
                    "id": _job_id(job_url),
                    "title": title_el.text.strip(),
                    "company": company_el.text.strip() if company_el else "Unknown",
                    "location": loc_el.text.strip() if loc_el else location,
                    "url": job_url,
                    "source": "naukri",
                    "description": "",
                    "status": "found",
                })
            except Exception:
                continue
        return jobs


# ── Indeed ──────────────────────────────────────────────────────────────────

def _search_indeed(role: str, location: str) -> list[dict]:
    # Indeed blocks automated scraping — use DuckDuckGo web search as fallback
    from web_search import search_jobs_web
    return search_jobs_web(role, location)


# ── Description Fetch ────────────────────────────────────────────────────────

def fetch_description(job: dict) -> str:
    try:
        resp = requests.get(job["url"], headers=_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        if job["source"] == "linkedin":
            el = soup.select_one("div.description__text")
        elif job["source"] == "naukri":
            el = soup.select_one("div.job-desc")
        else:
            el = soup.select_one("div#jobDescriptionText")
        return el.get_text(" ", strip=True)[:3000] if el else ""
    except Exception:
        return ""


# ── LinkedIn Posts Scrape for HR Emails ─────────────────────────────────────

async def _scrape_linkedin_posts_async(role: str, email: str, password: str) -> list[str]:
    """Login to LinkedIn, search posts for role, extract emails from post text."""
    import re as _re
    from playwright.async_api import async_playwright
    EMAIL_RE = _re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    emails = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("https://www.linkedin.com/login", timeout=20000)
            await page.fill("#username", email)
            await page.fill("#password", password)
            await page.click("button[type='submit']")
            await page.wait_for_timeout(3000)
            # Search posts
            query = f"{role} hiring email cv resume"
            await page.goto(
                f"https://www.linkedin.com/search/results/content/?keywords={query.replace(' ', '%20')}&origin=GLOBAL_SEARCH_HEADER",
                timeout=20000
            )
            await page.wait_for_timeout(3000)
            content = await page.content()
            emails = EMAIL_RE.findall(content)
        except Exception as e:
            print(f"  LinkedIn post scrape error: {e}")
        finally:
            await browser.close()
    seen = set()
    unique = []
    for e in emails:
        e = e.lower()
        skip = {"linkedin.com", "example.com", "noreply"}
        if not any(s in e for s in skip) and e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def scrape_linkedin_posts_for_emails(role: str) -> list[str]:
    """Sync wrapper for LinkedIn post email extraction."""
    import asyncio, os
    li_email = os.getenv("LINKEDIN_EMAIL")
    li_pass = os.getenv("LINKEDIN_PASSWORD")
    if not (li_email and li_pass):
        return []
    try:
        return asyncio.run(_scrape_linkedin_posts_async(role, li_email, li_pass))
    except Exception:
        return []


# ── Main Search ──────────────────────────────────────────────────────────────

def search_all_jobs() -> list[dict]:
    seen_ids = set()
    all_jobs = []

    searchers = [_search_linkedin, _search_naukri, _search_indeed]
    labels = ["LinkedIn", "Naukri", "Web"]

    # PAN India search only — broader results
    search_locations = ["India"]

    for role in TARGET_ROLES:
        for location in search_locations:
            for fn, label in zip(searchers, labels):
                try:
                    jobs = fn(role, location)
                    print(f"  {label}: {len(jobs)} results for '{role}' in {location}")
                    for j in jobs:
                        if j["id"] not in seen_ids:
                            seen_ids.add(j["id"])
                            all_jobs.append(j)
                    _sleep()
                except Exception as e:
                    print(f"  {label} error for '{role}': {e}")

    return all_jobs

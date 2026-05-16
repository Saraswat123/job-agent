"""
DuckDuckGo / Bing web search for HR contacts and job postings.
No API key required.
"""
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

ua = UserAgent()

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _headers():
    return {
        "User-Agent": ua.random,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8))
def ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo HTML search. Returns list of {title, url, snippet}."""
    resp = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers=_headers(),
        timeout=12,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for r in soup.select(".result")[:max_results]:
        title_el = r.select_one(".result__title")
        url_el = r.select_one(".result__url")
        snippet_el = r.select_one(".result__snippet")
        results.append({
            "title": title_el.get_text(strip=True) if title_el else "",
            "url": url_el.get_text(strip=True) if url_el else "",
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
    return results


def search_hr_email(company: str):
    """Search web for company HR/recruitment email. Returns first found or None."""
    query = f'"{company}" HR email recruitment careers apply India'
    try:
        results = ddg_search(query, max_results=5)
        combined = " ".join(r["snippet"] + " " + r["title"] for r in results)
        emails = EMAIL_RE.findall(combined)
        # Filter noise
        skip = {"noreply", "example", "test", "sentry", "linkedin", "naukri"}
        for email in emails:
            if not any(s in email for s in skip):
                return email.lower()
    except Exception:
        pass
    return None


def search_linkedin_posts_for_emails(role: str, location: str = "India") -> list:
    """
    Search web for LinkedIn posts about job role with email addresses.
    Returns list of emails found in snippets.
    """
    queries = [
        f'site:linkedin.com "{role}" "email" OR "send cv" OR "share resume" {location}',
        f'"{role}" "send your cv" OR "email us" site:linkedin.com {location}',
    ]
    emails = []
    for q in queries:
        try:
            results = ddg_search(q, max_results=5)
            combined = " ".join(r["snippet"] for r in results)
            found = EMAIL_RE.findall(combined)
            emails.extend(found)
            time.sleep(random.uniform(1, 2.5))
        except Exception:
            pass
    # Deduplicate
    seen = set()
    unique = []
    for e in emails:
        e = e.lower()
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def search_jobs_web(role: str, location: str = "Odisha India") -> list[dict]:
    """
    Fallback job search via web for when scrapers fail.
    Returns minimal job dicts.
    """
    import hashlib
    query = f'"{role}" jobs {location} site:naukri.com OR site:linkedin.com OR site:indeed.co.in'
    results = ddg_search(query, max_results=10)
    jobs = []
    for r in results:
        if not r["url"]:
            continue
        jobs.append({
            "id": hashlib.md5(r["url"].encode()).hexdigest()[:16],
            "title": role,
            "company": "Unknown",
            "location": location,
            "url": "https://" + r["url"] if not r["url"].startswith("http") else r["url"],
            "source": "web",
            "description": r["snippet"],
            "status": "found",
        })
    return jobs

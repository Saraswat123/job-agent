"""
Extract HR email addresses from job descriptions, LinkedIn posts, and company websites.
Uses regex + web search (no API key needed).
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

# Domains to ignore (not HR emails)
SKIP_DOMAINS = {
    "example.com", "test.com", "noreply.com", "no-reply.com",
    "sentry.io", "linkedin.com", "naukri.com", "indeed.com",
    "google.com", "gmail.com", "yahoo.com", "hotmail.com",
    "placeholder.com", "email.com",
}

HR_KEYWORDS = [
    "hr", "recruit", "talent", "career", "hiring", "people",
    "human", "resource", "jobs", "apply", "work",
]


def extract_from_text(text: str) -> list[str]:
    """Pull all emails from raw text, filter noise."""
    found = EMAIL_RE.findall(text or "")
    result = []
    seen = set()
    for email in found:
        email = email.lower().strip(".,;")
        domain = email.split("@")[-1]
        if domain in SKIP_DOMAINS:
            continue
        if email in seen:
            continue
        seen.add(email)
        result.append(email)
    # Prefer HR-looking emails first
    result.sort(key=lambda e: (
        0 if any(kw in e for kw in HR_KEYWORDS) else 1
    ))
    return result


def _headers():
    return {"User-Agent": ua.random, "Accept-Language": "en-US,en;q=0.9"}


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=6))
def search_duckduckgo(query: str) -> str:
    """Search DuckDuckGo HTML interface, return page text."""
    url = "https://html.duckduckgo.com/html/"
    resp = requests.post(url, data={"q": query}, headers=_headers(), timeout=12)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    texts = []
    for result in soup.select(".result__body")[:5]:
        texts.append(result.get_text(" ", strip=True))
    return " ".join(texts)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=6))
def fetch_page_emails(url: str) -> list[str]:
    """Fetch a URL and extract emails from its HTML."""
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        return extract_from_text(resp.text)
    except Exception:
        return []


def find_company_hr_email(company: str, job_title: str = ""):
    """
    Multi-strategy HR email finder.
    1. Search web for company HR email
    2. Try company careers page
    Returns best email or None.
    """
    emails = []

    # Strategy 1: DuckDuckGo search
    queries = [
        f'"{company}" HR email careers jobs',
        f'"{company}" recruitment email apply',
        f'"{company}" "hr@" OR "careers@" OR "recruit@"',
    ]
    for q in queries:
        try:
            text = search_duckduckgo(q)
            found = extract_from_text(text)
            emails.extend(found)
            if emails:
                break
            time.sleep(random.uniform(1.5, 3))
        except Exception:
            pass

    # Strategy 2: Company website careers page
    slug = company.lower().replace(" ", "").replace(".", "").replace(",", "")
    for domain_guess in [f"{slug}.com", f"{slug}.in", f"{slug}.co.in"]:
        for path in ["/careers", "/jobs", "/contact"]:
            try:
                found = fetch_page_emails(f"https://{domain_guess}{path}")
                emails.extend(found)
            except Exception:
                pass

    # Deduplicate and return best
    seen = set()
    unique = []
    for e in emails:
        if e not in seen:
            seen.add(e)
            unique.append(e)

    unique.sort(key=lambda e: (
        0 if any(kw in e for kw in HR_KEYWORDS) else 1
    ))

    return unique[0] if unique else None

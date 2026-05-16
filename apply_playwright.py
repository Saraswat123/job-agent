"""
Browser-based auto-fill AND auto-submit for LinkedIn Easy Apply and Naukri.
Uses persistent Chromium profile — log in once, sessions saved to disk.
No confirmation gate — submits automatically.
"""
import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

PROFILE_PATH = Path(__file__).parent / "candidate_profile.json"
CV_PATH = Path(__file__).parent / "assets" / "Dillip_Kumar_Das_CV.pdf"
BROWSER_PROFILE_DIR = Path(__file__).parent / "browser_profile"

profile = json.loads(PROFILE_PATH.read_text())
p = profile["personal"]

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD")


async def _fill_form_fields(page, cover_letter: str):
    for field in await page.locator("input[type='text'], input[type='tel'], input[type='number']").all():
        try:
            label = (await field.get_attribute("aria-label") or "").lower()
            placeholder = (await field.get_attribute("placeholder") or "").lower()
            hint = label + placeholder
            val = await field.input_value()
            if val:
                continue
            if "phone" in hint or "mobile" in hint:
                await field.fill(p["phone"].replace("+91 ", ""))
            elif "email" in hint:
                await field.fill(p["email"])
            elif "city" in hint or "location" in hint:
                await field.fill("Bhubaneswar")
            elif "experience" in hint and ("year" in hint or "exp" in hint):
                await field.fill(str(profile["experience_years"]))
            elif "salary" in hint or "ctc" in hint or "lpa" in hint:
                await field.fill("1500000")
            elif "notice" in hint:
                await field.fill("30")
            elif "name" in hint and "first" in hint:
                await field.fill("Dillip Kumar")
            elif "name" in hint and "last" in hint:
                await field.fill("Das")
            elif "name" in hint:
                await field.fill(p["name"])
        except Exception:
            continue

    for ta in await page.locator("textarea").all():
        try:
            if await ta.is_visible():
                val = await ta.input_value()
                if not val:
                    await ta.fill(cover_letter[:1500])
        except Exception:
            continue

    upload = page.locator("input[type='file']")
    if await upload.count() > 0 and CV_PATH.exists():
        try:
            await upload.set_input_files(str(CV_PATH))
            await page.wait_for_timeout(1000)
        except Exception:
            pass


async def _linkedin_easy_apply(page, job_url: str, cover_letter: str) -> bool:
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        apply_btn = page.locator("button.jobs-apply-button")
        if not await apply_btn.is_visible():
            # Try alternate selectors
            apply_btn = page.locator("button[data-control-name='jobdetails_topcard_inapply']")
            if not await apply_btn.is_visible():
                print("    No Easy Apply button found")
                return False
        await apply_btn.click()
        await page.wait_for_timeout(1500)

        for _ in range(15):
            await _fill_form_fields(page, cover_letter)

            submit_btn = page.locator("button[aria-label='Submit application']")
            review_btn = page.locator("button[aria-label='Review your application']")
            next_btn = page.locator("button[aria-label='Continue to next step']")

            if await submit_btn.is_visible():
                await submit_btn.click()
                await page.wait_for_timeout(2000)
                return True
            elif await review_btn.is_visible():
                await review_btn.click()
            elif await next_btn.is_visible():
                await next_btn.click()
            else:
                break

            await page.wait_for_timeout(1500)

        return False
    except Exception as e:
        print(f"    LinkedIn Easy Apply error: {e}")
        return False


async def _naukri_apply(page, job_url: str, cover_letter: str) -> bool:
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        apply_btn = page.locator("button:has-text('Apply'), a:has-text('Apply Now')")
        if not await apply_btn.first.is_visible():
            return False
        await apply_btn.first.click()
        await page.wait_for_timeout(2000)

        login_modal = page.locator("div.loginModal, div#login-layer")
        if await login_modal.is_visible():
            await page.fill("input[placeholder*='Email']", NAUKRI_EMAIL)
            await page.fill("input[placeholder*='Password']", NAUKRI_PASSWORD)
            await page.click("button[type='submit']:has-text('Login')")
            await page.wait_for_timeout(3000)
            await apply_btn.first.click()
            await page.wait_for_timeout(2000)

        await _fill_form_fields(page, cover_letter)

        submit = page.locator("button:has-text('Submit'), button:has-text('Apply')")
        if await submit.first.is_visible():
            await submit.first.click()
            await page.wait_for_timeout(2000)
            return True

        return False
    except Exception as e:
        print(f"    Naukri apply error: {e}")
        return False


async def _ensure_linkedin_login(context, page):
    """
    Check if logged in. If not, navigate to login page and wait for
    user to log in manually (up to 3 minutes).
    Returns True when logged in.
    """
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    current = page.url
    if "feed" in current or "mynetwork" in current or "jobs" in current:
        print("    LinkedIn: already logged in (profile saved)")
        return True

    print("    LinkedIn: not logged in — opening login page...")
    print("    >>> Please log in to LinkedIn in the browser window. Waiting up to 3 minutes...")
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=15000)

    # Pre-fill credentials if available
    try:
        if LINKEDIN_EMAIL:
            await page.fill("#username", LINKEDIN_EMAIL)
        if LINKEDIN_PASSWORD:
            await page.fill("#password", LINKEDIN_PASSWORD)
            await page.click("button[type='submit']")
    except Exception:
        pass

    # Wait for user to complete login (handles 2FA, CAPTCHA, etc.)
    for _ in range(36):  # 36 * 5s = 3 minutes
        await page.wait_for_timeout(5000)
        url = page.url
        if "feed" in url or "mynetwork" in url or "jobs" in url:
            print("    LinkedIn: login successful — session saved to browser_profile/")
            return True
        if "checkpoint" in url or "challenge" in url:
            print("    LinkedIn: security challenge detected — please complete in browser")

    print("    LinkedIn: login timed out")
    return False


async def apply_to_job(job: dict, cover_letter: str) -> bool:
    source = job.get("source", "")
    url = job.get("url", "")

    BROWSER_PROFILE_DIR.mkdir(exist_ok=True)

    async with async_playwright() as pw:
        # Persistent context — saves cookies/session to disk automatically
        context = await pw.chromium.launch_persistent_context(
            str(BROWSER_PROFILE_DIR),
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            java_script_enabled=True,
        )

        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};
        """)

        result = False

        try:
            if source == "linkedin":
                logged_in = await _ensure_linkedin_login(context, page)
                if logged_in:
                    result = await _linkedin_easy_apply(page, url, cover_letter)

            elif source == "naukri" and NAUKRI_EMAIL:
                result = await _naukri_apply(page, url, cover_letter)

            else:
                print(f"    No browser-apply handler for source: {source}")

        except Exception as e:
            print(f"    apply_to_job error: {e}")
        finally:
            await context.close()

    return result


def apply_sync(job: dict, cover_letter: str) -> bool:
    return asyncio.run(apply_to_job(job, cover_letter))


async def setup_linkedin_session():
    """
    Standalone: open browser, wait for manual LinkedIn login, save session.
    Run once: python -c "from apply_playwright import setup_linkedin_session; import asyncio; asyncio.run(setup_linkedin_session())"
    """
    BROWSER_PROFILE_DIR.mkdir(exist_ok=True)
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            str(BROWSER_PROFILE_DIR),
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        print("Opening LinkedIn login...")
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        if LINKEDIN_EMAIL:
            try:
                await page.fill("#username", LINKEDIN_EMAIL)
                await page.fill("#password", LINKEDIN_PASSWORD)
                await page.click("button[type='submit']")
            except Exception:
                pass

        print(">>> Log in to LinkedIn in the browser. Waiting up to 5 minutes...")
        for _ in range(60):
            await page.wait_for_timeout(5000)
            url = page.url
            if "feed" in url or "mynetwork" in url:
                print("✓ Logged in! Session saved to browser_profile/")
                print("  Future runs will NOT need manual login.")
                break
            if "checkpoint" in url or "challenge" in url:
                print("  Security check — complete it in the browser window")
        else:
            print("✗ Login timed out")

        await context.close()


if __name__ == "__main__":
    asyncio.run(setup_linkedin_session())

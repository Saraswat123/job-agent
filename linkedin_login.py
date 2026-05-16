"""
Extracts LinkedIn cookies from Comet browser.
Decrypts macOS AES-CBC encrypted cookies via Keychain.
Run: python linkedin_login.py
"""
import json
import shutil
import sqlite3
import subprocess
import tempfile
import hashlib
from pathlib import Path

SESSION_FILE = Path(__file__).parent / "linkedin_session.json"
COMET_COOKIES_DB = Path.home() / "Library/Application Support/Comet/Default/Cookies"


def get_aes_key():
    for service in ["Comet Safe Storage", "Chrome Safe Storage", "Chromium Safe Storage"]:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True
        )
        if r.returncode == 0 and r.stdout.strip():
            password = r.stdout.strip().encode()
            return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)
    return None


def decrypt_value(enc: bytes, key: bytes) -> str:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    if enc[:3] == b"v10":
        enc = enc[3:]

    cipher = Cipher(algorithms.AES(key), modes.CBC(b" " * 16), backend=default_backend())
    dec = cipher.decryptor()
    raw = dec.update(enc) + dec.finalize()

    # Remove PKCS7 padding
    pad = raw[-1]
    if 1 <= pad <= 16:
        raw = raw[:-pad]

    # Valid HTTP cookie value chars (RFC 6265): printable ASCII except " , ; \
    VALID = set(range(0x21, 0x7F)) - {0x22, 0x2C, 0x3B, 0x5C}

    # Find first run of 8+ consecutive valid cookie chars (skip junk prefix)
    best_start = len(raw)
    run_start = None
    for i, b in enumerate(raw):
        if b in VALID:
            if run_start is None:
                run_start = i
            if i - run_start >= 7:  # 8 consecutive valid chars found
                best_start = run_start
                break
        else:
            run_start = None

    return raw[best_start:].decode("ascii", errors="ignore")


def extract_linkedin_cookies():
    if not COMET_COOKIES_DB.exists():
        print(f"ERROR: DB not found: {COMET_COOKIES_DB}")
        return None

    key = get_aes_key()
    if not key:
        print("ERROR: Could not get decryption key from macOS Keychain")
        return None
    print("✓ AES key derived from Keychain")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as t:
        tmp = t.name
    shutil.copy2(str(COMET_COOKIES_DB), tmp)

    conn = sqlite3.connect(tmp)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT name, value, encrypted_value, host_key, path,
               is_secure, expires_utc, is_httponly
        FROM cookies WHERE host_key LIKE '%linkedin.com%'
    """).fetchall()
    conn.close()
    Path(tmp_path := tmp).unlink(missing_ok=True)

    cookies = []
    for row in rows:
        enc = bytes(row["encrypted_value"])
        if enc and len(enc) > 3:
            value = decrypt_value(enc, key)
        else:
            value = row["value"] or ""

        expires = row["expires_utc"]
        expires_unix = (expires - 11644473600000000) / 1000000 if expires > 0 else -1
        host = row["host_key"]

        cookies.append({
            "name": row["name"],
            "value": value,
            "domain": host if host.startswith(".") else "." + host,
            "path": row["path"] or "/",
            "secure": bool(row["is_secure"]),
            "httpOnly": bool(row["is_httponly"]),
            "expires": expires_unix,
            "sameSite": "None",
        })

    print(f"Decrypted {len(cookies)} LinkedIn cookies")

    key_list = ["li_at", "JSESSIONID", "bcookie"]
    cookie_map = {c["name"]: c["value"] for c in cookies}
    all_ok = True
    for k in key_list:
        v = cookie_map.get(k, "")
        ok = bool(v) and v[0].isascii() and v[0].isprintable()
        print(f"  {k}: {'✓ ' + v[:35] + '...' if ok else '✗ empty/corrupt'}")
        if not ok:
            all_ok = False

    state = {"cookies": cookies, "origins": []}
    SESSION_FILE.write_text(json.dumps(state, indent=2))
    print(f"\n✓ Saved → {SESSION_FILE}")
    return state if all_ok else None


if __name__ == "__main__":
    result = extract_linkedin_cookies()
    if result:
        print("Testing session with Playwright...")
        import asyncio
        from playwright.async_api import async_playwright

        async def test():
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                ctx = await browser.new_context()
                await ctx.add_cookies(result["cookies"])
                page = await ctx.new_page()
                await page.goto("https://www.linkedin.com/feed/", timeout=20000)
                await page.wait_for_timeout(2000)
                url = page.url
                print(f"LinkedIn URL after session inject: {url}")
                if "feed" in url:
                    print("✓ Session VALID — LinkedIn Easy Apply will work!")
                else:
                    print("✗ Session invalid — still redirecting to login")
                await browser.close()

        asyncio.run(test())

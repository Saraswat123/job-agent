"""
Run ONCE to authorize Gmail API access.
Creates token.json which gmail_sender.py uses.

Prerequisites:
1. Go to console.cloud.google.com
2. Create project > Enable Gmail API
3. Credentials > OAuth 2.0 Client ID > Desktop App
4. Download as credentials.json into this folder
5. Run: python gmail_setup.py
"""
import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

BASE = Path(__file__).parent
CREDS_FILE = BASE / "credentials.json"
TOKEN_FILE = BASE / "token.json"


def authorize():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                print("ERROR: credentials.json not found.")
                print("Download from Google Cloud Console > APIs & Services > Credentials")
                return
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())
        print(f"✓ Token saved to {TOKEN_FILE}")

    print("✓ Gmail authorization complete. You can now run daily_agent.py")


if __name__ == "__main__":
    authorize()

"""
Gmail API wrapper — sends emails directly (not drafts).
Every application email auto-attaches CV PDF.
"""
import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

BASE = Path(__file__).parent
TOKEN_FILE = BASE / "token.json"
CV_PATH = BASE / "assets" / "Dillip_Kumar_Das_CV.pdf"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

SENDER = os.getenv("GMAIL_SENDER_ADDRESS", "dillip.das4@gmail.com")


def _get_service():
    if not TOKEN_FILE.exists():
        raise RuntimeError("token.json not found. Run gmail_setup.py first.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def send_application_email(
    to: str,
    subject: str,
    cover_letter: str,
    attach_cv: bool = True,
) -> bool:
    """Send application email with optional CV attachment."""
    msg = MIMEMultipart()
    msg["From"] = SENDER
    msg["To"] = to
    msg["Subject"] = subject

    msg.attach(MIMEText(cover_letter, "plain"))

    if attach_cv and CV_PATH.exists():
        with open(CV_PATH, "rb") as f:
            part = MIMEApplication(f.read(), Name="Dillip_Kumar_Das_CV.pdf")
        part["Content-Disposition"] = 'attachment; filename="Dillip_Kumar_Das_CV.pdf"'
        msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        service = _get_service()
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return True
    except Exception as e:
        print(f"  Gmail send failed: {e}")
        return False


def send_followup_email(to: str, subject: str, body: str) -> bool:
    return send_application_email(to, subject, body, attach_cv=False)


def draft_application_email(
    to: str,
    subject: str,
    cover_letter: str,
) -> bool:
    """Save as Gmail draft instead of sending."""
    msg = MIMEMultipart()
    msg["From"] = SENDER
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(cover_letter, "plain"))

    if CV_PATH.exists():
        with open(CV_PATH, "rb") as f:
            part = MIMEApplication(f.read(), Name="Dillip_Kumar_Das_CV.pdf")
        part["Content-Disposition"] = 'attachment; filename="Dillip_Kumar_Das_CV.pdf"'
        msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        service = _get_service()
        service.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}
        ).execute()
        return True
    except Exception as e:
        print(f"  Gmail draft failed: {e}")
        return False

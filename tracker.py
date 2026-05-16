"""
SQLite-backed job tracker — prevents duplicate applications, stores state.
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "outbox" / "jobs.db"


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT PRIMARY KEY,
                title       TEXT,
                company     TEXT,
                location    TEXT,
                source      TEXT,
                url         TEXT,
                match_score INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'found',
                applied_at  TEXT,
                cover_letter TEXT,
                notes       TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS followups (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT,
                follow_date TEXT,
                sent        INTEGER DEFAULT 0,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
        """)


def is_duplicate(job_id: str, cooldown_days: int = 30) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT applied_at FROM jobs WHERE id=? AND status='applied'", (job_id,)
        ).fetchone()
        if not row:
            return False
        if row["applied_at"]:
            applied = datetime.fromisoformat(row["applied_at"])
            return (datetime.now() - applied).days < cooldown_days
        return False


def upsert_job(job: dict):
    with _conn() as c:
        c.execute("""
            INSERT INTO jobs (id, title, company, location, source, url, match_score, status)
            VALUES (:id, :title, :company, :location, :source, :url, :match_score, :status)
            ON CONFLICT(id) DO UPDATE SET
                match_score = excluded.match_score,
                status = CASE WHEN jobs.status='applied' THEN jobs.status ELSE excluded.status END
        """, job)


def mark_applied(job_id: str, cover_letter: str = ""):
    with _conn() as c:
        c.execute(
            "UPDATE jobs SET status='applied', applied_at=?, cover_letter=? WHERE id=?",
            (datetime.now().isoformat(), cover_letter, job_id)
        )
        follow_date = (datetime.now() + timedelta(days=7)).date().isoformat()
        c.execute(
            "INSERT INTO followups (job_id, follow_date) VALUES (?, ?)",
            (job_id, follow_date)
        )


def mark_skipped(job_id: str, reason: str = ""):
    with _conn() as c:
        c.execute(
            "UPDATE jobs SET status='skipped', notes=? WHERE id=?",
            (reason, job_id)
        )


def get_pending_followups() -> list[dict]:
    today = datetime.now().date().isoformat()
    with _conn() as c:
        rows = c.execute("""
            SELECT f.id, f.job_id, j.company, j.title, j.url
            FROM followups f JOIN jobs j ON f.job_id = j.id
            WHERE f.follow_date <= ? AND f.sent = 0
        """, (today,)).fetchall()
        return [dict(r) for r in rows]


def mark_followup_sent(followup_id: int):
    with _conn() as c:
        c.execute("UPDATE followups SET sent=1 WHERE id=?", (followup_id,))


def daily_stats() -> dict:
    today = datetime.now().date().isoformat()
    with _conn() as c:
        applied_today = c.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='applied' AND applied_at LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]
        total_applied = c.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='applied'"
        ).fetchone()[0]
        total_found = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    return {
        "applied_today": applied_today,
        "total_applied": total_applied,
        "total_found": total_found,
    }


def export_shortlist(jobs: list[dict], date_str: str):
    out = Path(__file__).parent / "outbox" / f"shortlist_{date_str}.json"
    out.write_text(json.dumps(jobs, indent=2))
    return str(out)


init_db()

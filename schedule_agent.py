"""
Keep-alive scheduler — runs daily_agent.py every day at configured time.
Run in background: python schedule_agent.py &
Or use system cron: 0 8 * * * cd /path/to/job-agent && python daily_agent.py
"""
import schedule
import time
import subprocess
import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level="INFO",
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scheduler.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

RUN_TIME = os.getenv("AGENT_RUN_TIME", "08:00")
AGENT_SCRIPT = str(Path(__file__).parent / "daily_agent.py")


def run_agent():
    log.info("Scheduler: triggering daily_agent.py")
    result = subprocess.run(
        [sys.executable, AGENT_SCRIPT],
        capture_output=False,
        cwd=str(Path(__file__).parent),
    )
    if result.returncode != 0:
        log.error(f"daily_agent.py exited with code {result.returncode}")
    else:
        log.info("daily_agent.py completed successfully")


def main():
    log.info(f"Scheduler started — running agent daily at {RUN_TIME}")
    schedule.every().day.at(RUN_TIME).do(run_agent)

    if "--run-now" in sys.argv:
        run_agent()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()

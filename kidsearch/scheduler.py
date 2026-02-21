"""
CrawlScheduler — background crawl scheduling using APScheduler.

Reads/writes data/scheduler.json to coordinate with the Dashboard.
A watchdog thread resyncs the APScheduler job every 60 s when the
config file changes (file-based IPC between start.py and Streamlit).
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"
SCHEDULER_FILE = _DATA_DIR / "scheduler.json"
PID_FILE = _DATA_DIR / "crawler.pid"
CRAWLER_SCRIPT = Path(__file__).parent.parent / "crawler.py"

DEFAULT_CONFIG: dict = {
    "enabled": False,
    "days_of_week": [0, 1, 2, 3, 4, 5, 6],  # 0=Mon … 6=Sun
    "hour": 3,
    "minute": 0,
    "options": {
        "site": None,
        "force": False,
        "workers": 2,
        "embeddings": True,
        "persistent_cache": False,
    },
    "last_run": None,
    "next_run": None,
}

# APScheduler day_of_week strings (0=Mon, same as Python weekday())
_DOW_MAP = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


class CrawlScheduler:
    """Manages the background APScheduler job for automatic crawls."""

    def __init__(self):
        self._scheduler = None
        self._current_config_key = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def load_config(self) -> dict:
        try:
            if SCHEDULER_FILE.exists():
                with open(SCHEDULER_FILE) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"[Scheduler] Could not read config: {e}")
        return dict(DEFAULT_CONFIG)

    def _save_config(self, config: dict) -> None:
        try:
            SCHEDULER_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SCHEDULER_FILE, "w") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"[Scheduler] Could not save config: {e}")

    # ------------------------------------------------------------------
    # Crawl launcher (no Streamlit dependency)
    # ------------------------------------------------------------------

    def _is_crawler_running(self) -> bool:
        if not PID_FILE.exists():
            return False
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ValueError, OSError):
            PID_FILE.unlink(missing_ok=True)
            return False

    def _launch_crawl(self, options: dict) -> None:
        if self._is_crawler_running():
            logger.info("[Scheduler] Crawler already running — skipping scheduled run")
            return

        cmd = [sys.executable, str(CRAWLER_SCRIPT)]
        if options.get("site"):
            cmd.extend(["--site", options["site"]])
        if options.get("force"):
            cmd.append("--force")
        if options.get("workers"):
            cmd.extend(["--workers", str(options["workers"])])
        if options.get("embeddings"):
            cmd.append("--embeddings")
        if options.get("persistent_cache"):
            cmd.append("--persistent-cache")

        logger.info(f"[Scheduler] Launching scheduled crawl: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(cmd)
            PID_FILE.write_text(str(process.pid))
            config = self.load_config()
            config["last_run"] = datetime.now().isoformat()
            self._save_config(config)
        except Exception as e:
            logger.error(f"[Scheduler] Failed to launch crawl: {e}")

    # ------------------------------------------------------------------
    # APScheduler job management
    # ------------------------------------------------------------------

    def _config_key(self, config: dict) -> tuple:
        return (
            config.get("enabled"),
            tuple(sorted(config.get("days_of_week", []))),
            config.get("hour"),
            config.get("minute"),
        )

    def _sync_job(self) -> None:
        """Resync the APScheduler job when the config file has changed."""
        config = self.load_config()
        key = self._config_key(config)
        if key == self._current_config_key:
            return

        with self._lock:
            if self._scheduler.get_job("scheduled_crawl"):
                self._scheduler.remove_job("scheduled_crawl")

            if config.get("enabled"):
                days = config.get("days_of_week", list(range(7)))
                dow_str = (
                    ",".join(_DOW_MAP[d] for d in sorted(days) if d in _DOW_MAP)
                    or "mon-sun"
                )

                from apscheduler.triggers.cron import CronTrigger

                trigger = CronTrigger(
                    day_of_week=dow_str,
                    hour=config.get("hour", 3),
                    minute=config.get("minute", 0),
                )
                self._scheduler.add_job(
                    self._launch_crawl,
                    trigger=trigger,
                    args=[config.get("options", {})],
                    id="scheduled_crawl",
                    replace_existing=True,
                )
                job = self._scheduler.get_job("scheduled_crawl")
                if job and job.next_run_time:
                    config["next_run"] = job.next_run_time.isoformat()
                    self._save_config(config)

                logger.info(
                    f"[Scheduler] Job updated: days={dow_str} "
                    f"{config.get('hour', 3):02d}:{config.get('minute', 0):02d}"
                )
            else:
                config["next_run"] = None
                self._save_config(config)
                logger.info("[Scheduler] Scheduled crawl disabled")

            self._current_config_key = key

    def _watchdog(self) -> None:
        while True:
            try:
                self._sync_job()
            except Exception as e:
                logger.error(f"[Scheduler] Watchdog error: {e}")
            time.sleep(60)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            logger.warning(
                "[Scheduler] APScheduler not installed — scheduled crawls disabled. "
                "Run: pip install APScheduler>=3.10.0"
            )
            return

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

        thread = threading.Thread(
            target=self._watchdog, daemon=True, name="crawl-scheduler-watchdog"
        )
        thread.start()
        logger.info("[Scheduler] CrawlScheduler started")

    def stop(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("[Scheduler] CrawlScheduler stopped")

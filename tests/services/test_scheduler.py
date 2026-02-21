"""
Tests for kidsearch.scheduler.CrawlScheduler
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scheduler(sched_file: Path, pid_file: Path):
    """Return a CrawlScheduler with its file paths redirected to tmp_path."""
    from kidsearch.scheduler import CrawlScheduler

    scheduler = CrawlScheduler()
    # Patch module-level path constants used inside the instance methods
    scheduler._sched_file = sched_file
    scheduler._pid_file = pid_file
    return scheduler


# We patch at the module level so every method picks up the tmp paths.
def _patched(monkeypatch, tmp_path):
    """Apply monkeypatches and return a fresh CrawlScheduler."""
    sched = tmp_path / "scheduler.json"
    pid = tmp_path / "crawler.pid"

    monkeypatch.setattr("kidsearch.scheduler.SCHEDULER_FILE", sched)
    monkeypatch.setattr("kidsearch.scheduler.PID_FILE", pid)
    monkeypatch.setattr("kidsearch.scheduler.CRAWLER_SCRIPT", Path(sys.executable))

    # Reload the module constants used inside the class body
    from kidsearch.scheduler import CrawlScheduler

    return CrawlScheduler(), sched, pid


# ---------------------------------------------------------------------------
# Config — load
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_returns_default_when_no_file(self, monkeypatch, tmp_path):
        scheduler, sched, _ = _patched(monkeypatch, tmp_path)
        from kidsearch.scheduler import DEFAULT_CONFIG

        config = scheduler.load_config()
        assert config == DEFAULT_CONFIG

    def test_reads_existing_file(self, monkeypatch, tmp_path):
        scheduler, sched, _ = _patched(monkeypatch, tmp_path)
        payload = {"enabled": True, "hour": 5, "minute": 30, "days_of_week": [1, 3]}
        sched.write_text(json.dumps(payload))

        config = scheduler.load_config()
        assert config["enabled"] is True
        assert config["hour"] == 5

    def test_falls_back_to_default_on_corrupt_json(self, monkeypatch, tmp_path):
        scheduler, sched, _ = _patched(monkeypatch, tmp_path)
        from kidsearch.scheduler import DEFAULT_CONFIG

        sched.write_text("{ this is not valid json }")
        config = scheduler.load_config()
        assert config == DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Config — save
# ---------------------------------------------------------------------------


class TestSaveConfig:
    def test_creates_directory_if_missing(self, monkeypatch, tmp_path):
        nested_file = tmp_path / "deep" / "dir" / "scheduler.json"
        monkeypatch.setattr("kidsearch.scheduler.SCHEDULER_FILE", nested_file)
        monkeypatch.setattr("kidsearch.scheduler.PID_FILE", tmp_path / "crawler.pid")

        from kidsearch.scheduler import CrawlScheduler

        s = CrawlScheduler()
        s._save_config({"enabled": False})
        assert nested_file.exists()

    def test_writes_valid_json(self, monkeypatch, tmp_path):
        scheduler, sched, _ = _patched(monkeypatch, tmp_path)
        payload = {"enabled": True, "hour": 2, "minute": 0}
        scheduler._save_config(payload)

        written = json.loads(sched.read_text())
        assert written == payload


# ---------------------------------------------------------------------------
# PID / process detection
# ---------------------------------------------------------------------------


class TestIsCrawlerRunning:
    def test_false_when_no_pid_file(self, monkeypatch, tmp_path):
        scheduler, _, pid = _patched(monkeypatch, tmp_path)
        assert scheduler._is_crawler_running() is False

    def test_false_and_removes_stale_pid(self, monkeypatch, tmp_path):
        scheduler, _, pid = _patched(monkeypatch, tmp_path)
        # Write a PID that does not exist
        pid.write_text("999999999")

        assert scheduler._is_crawler_running() is False
        assert not pid.exists()

    def test_true_for_current_process(self, monkeypatch, tmp_path):
        scheduler, _, pid = _patched(monkeypatch, tmp_path)
        pid.write_text(str(os.getpid()))

        assert scheduler._is_crawler_running() is True

    def test_false_for_invalid_pid_content(self, monkeypatch, tmp_path):
        scheduler, _, pid = _patched(monkeypatch, tmp_path)
        pid.write_text("not_a_number")

        assert scheduler._is_crawler_running() is False


# ---------------------------------------------------------------------------
# Crawl launcher
# ---------------------------------------------------------------------------


class TestLaunchCrawl:
    def test_skips_if_already_running(self, monkeypatch, tmp_path):
        scheduler, _, pid = _patched(monkeypatch, tmp_path)
        pid.write_text(str(os.getpid()))  # current process = "running"

        with patch("subprocess.Popen") as mock_popen:
            scheduler._launch_crawl({})
            mock_popen.assert_not_called()

    def test_basic_command_no_options(self, monkeypatch, tmp_path):
        scheduler, sched, pid = _patched(monkeypatch, tmp_path)
        sched.write_text(json.dumps({"enabled": True, "last_run": None}))

        fake_proc = MagicMock()
        fake_proc.pid = 42

        with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
            scheduler._launch_crawl({})
            cmd = mock_popen.call_args[0][0]

        assert sys.executable in cmd[0]
        assert "--force" not in cmd
        assert "--embeddings" not in cmd
        assert "--persistent-cache" not in cmd

    def test_all_options_included_in_command(self, monkeypatch, tmp_path):
        scheduler, sched, pid = _patched(monkeypatch, tmp_path)
        sched.write_text(json.dumps({"enabled": True, "last_run": None}))

        fake_proc = MagicMock()
        fake_proc.pid = 43

        options = {
            "site": "MySite",
            "force": True,
            "workers": 4,
            "embeddings": True,
            "persistent_cache": True,
        }

        with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
            scheduler._launch_crawl(options)
            cmd = mock_popen.call_args[0][0]

        assert "--site" in cmd
        assert "MySite" in cmd
        assert "--force" in cmd
        assert "--workers" in cmd
        assert "4" in cmd
        assert "--embeddings" in cmd
        assert "--persistent-cache" in cmd

    def test_writes_pid_file(self, monkeypatch, tmp_path):
        scheduler, sched, pid = _patched(monkeypatch, tmp_path)
        sched.write_text(json.dumps({"enabled": True, "last_run": None}))

        fake_proc = MagicMock()
        fake_proc.pid = 1234

        with patch("subprocess.Popen", return_value=fake_proc):
            scheduler._launch_crawl({})

        assert pid.exists()
        assert pid.read_text() == "1234"

    def test_updates_last_run_in_config(self, monkeypatch, tmp_path):
        scheduler, sched, pid = _patched(monkeypatch, tmp_path)
        sched.write_text(json.dumps({"enabled": True, "last_run": None}))

        fake_proc = MagicMock()
        fake_proc.pid = 99

        with patch("subprocess.Popen", return_value=fake_proc):
            scheduler._launch_crawl({})

        saved = json.loads(sched.read_text())
        assert saved["last_run"] is not None


# ---------------------------------------------------------------------------
# Config key
# ---------------------------------------------------------------------------


class TestConfigKey:
    def setup_method(self):
        from kidsearch.scheduler import CrawlScheduler

        self.scheduler = CrawlScheduler()

    def test_day_order_does_not_matter(self):
        c1 = {"enabled": True, "days_of_week": [0, 2, 4], "hour": 3, "minute": 0}
        c2 = {"enabled": True, "days_of_week": [4, 0, 2], "hour": 3, "minute": 0}
        assert self.scheduler._config_key(c1) == self.scheduler._config_key(c2)

    def test_different_hour_gives_different_key(self):
        c1 = {"enabled": True, "days_of_week": [0], "hour": 2, "minute": 0}
        c2 = {"enabled": True, "days_of_week": [0], "hour": 3, "minute": 0}
        assert self.scheduler._config_key(c1) != self.scheduler._config_key(c2)

    def test_different_days_gives_different_key(self):
        c1 = {"enabled": True, "days_of_week": [0, 1], "hour": 3, "minute": 0}
        c2 = {"enabled": True, "days_of_week": [0, 2], "hour": 3, "minute": 0}
        assert self.scheduler._config_key(c1) != self.scheduler._config_key(c2)

    def test_enabled_flag_changes_key(self):
        c1 = {"enabled": True, "days_of_week": [0], "hour": 3, "minute": 0}
        c2 = {"enabled": False, "days_of_week": [0], "hour": 3, "minute": 0}
        assert self.scheduler._config_key(c1) != self.scheduler._config_key(c2)

    def test_missing_days_defaults_gracefully(self):
        c = {"enabled": True, "hour": 3, "minute": 0}
        key = self.scheduler._config_key(c)
        assert isinstance(key, tuple)

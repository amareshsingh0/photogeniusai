import importlib

import pytest


def test_start_scheduler_skips_publish_job_by_default(monkeypatch) -> None:
    pytest.importorskip("apscheduler")
    monkeypatch.delenv("ENABLE_PUBLISH_SCHEDULER", raising=False)

    mod = importlib.import_module("app.tasks.scheduled")
    mod = importlib.reload(mod)

    jobs_before = {job.id for job in mod.scheduler.get_jobs()}
    mod.start_scheduler()
    jobs_after = {job.id for job in mod.scheduler.get_jobs()}

    assert "publish_due_tasks" not in jobs_after
    assert "daily_cleanup" in jobs_after
    assert "weekly_stats" in jobs_after

    mod.stop_scheduler()

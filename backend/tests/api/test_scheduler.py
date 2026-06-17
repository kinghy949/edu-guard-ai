from __future__ import annotations

from sqlalchemy import select

from app.models.system import JobRun, SystemSetting
from tests.conftest import auth_header, make_user


def _admin(db, *, username="sched_admin"):
    u = make_user(db, role="admin", username=username, password="GoodPass1")
    db.commit()
    return u


def test_get_warning_schedule_default(client, db):
    admin = _admin(db)
    r = client.get("/api/v1/admin/settings/warning-schedule", headers=auth_header(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["cron"]


def test_put_warning_schedule_invalid_cron_422(client, db):
    admin = _admin(db, username="sched_bad")
    r = client.put("/api/v1/admin/settings/warning-schedule",
                   json={"enabled": True, "cron": "not a cron"},
                   headers=auth_header(admin))
    assert r.status_code == 422


def test_put_warning_schedule_persists(client, db):
    admin = _admin(db, username="sched_put")
    payload = {"enabled": True, "cron": "0 4 * * 1", "scope": {"college": "信息学院"},
               "auto_dispatch": True, "channels": ["inbox", "email"]}
    r = client.put("/api/v1/admin/settings/warning-schedule",
                   json=payload, headers=auth_header(admin))
    assert r.status_code == 200
    row = db.get(SystemSetting, "warning_schedule")
    assert row and row.value["enabled"] is True
    assert row.value["cron"] == "0 4 * * 1"
    assert row.value["scope"]["college"] == "信息学院"


def test_run_now_writes_job_run_record(client, db):
    admin = _admin(db, username="sched_runnow")
    r = client.post("/api/v1/admin/jobs/generate-warnings/run-now",
                    headers=auth_header(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"success", "skipped", "failed"}
    # job_runs 表有记录（独立 SessionLocal 写入后 commit，主测试 db 也能看到）
    runs = list(db.scalars(
        select(JobRun).where(JobRun.job_name == "warning_schedule").order_by(JobRun.id.desc())
    ))
    assert runs, "job_runs 未生成"


def test_list_job_runs_returns_data(client, db):
    admin = _admin(db, username="sched_runs_list")
    # 触发两次
    for _ in range(2):
        client.post("/api/v1/admin/jobs/generate-warnings/run-now",
                    headers=auth_header(admin))
    r = client.get("/api/v1/admin/job-runs?limit=10", headers=auth_header(admin))
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 2
    assert all("status" in row and "job_name" in row for row in rows)


def test_only_admin_can_access_scheduler(client, db):
    counselor = make_user(db, role="counselor", username="sched_couns",
                          password="GoodPass1")
    db.commit()
    headers = auth_header(counselor)
    assert client.get("/api/v1/admin/settings/warning-schedule",
                      headers=headers).status_code == 403
    assert client.post("/api/v1/admin/jobs/generate-warnings/run-now",
                       headers=headers).status_code == 403

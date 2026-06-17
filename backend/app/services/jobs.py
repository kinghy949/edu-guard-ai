"""定时任务的具体实现，与 scheduler 解耦便于直接单测。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.student import Student
from app.models.system import SystemSetting
from app.models.warning import Warning
from app.services.notify_dispatcher import dispatch_warning
from app.services.warning_engine import generate_batch

log = get_logger("jobs")

SETTING_KEY = "warning_schedule"


def get_warning_schedule(db: Session) -> dict[str, Any]:
    row = db.get(SystemSetting, SETTING_KEY)
    if row and row.value:
        return row.value
    # 兜底默认
    return {
        "enabled": False,
        "cron": "0 3 * * 1",
        "scope": {},
        "auto_dispatch": False,
        "channels": ["inbox"],
    }


def set_warning_schedule(db: Session, value: dict[str, Any], updated_by: int | None) -> None:
    row = db.get(SystemSetting, SETTING_KEY)
    if row is None:
        db.add(SystemSetting(key=SETTING_KEY, value=value, updated_by=updated_by))
    else:
        row.value = value
        row.updated_by = updated_by


def job_generate_warnings(db: Session) -> dict[str, Any]:
    """定时生成预警；可选自动入队通知。"""
    cfg = get_warning_schedule(db)
    if not cfg.get("enabled"):
        log.info("job_warning_skipped", reason="disabled")
        return {"skipped": True, "reason": "disabled"}

    scope = cfg.get("scope") or {}
    stmt = select(Student)
    if scope.get("college"):
        stmt = stmt.where(Student.college == scope["college"])
    if scope.get("major"):
        stmt = stmt.where(Student.major == scope["major"])
    if scope.get("enroll_year") is not None:
        stmt = stmt.where(Student.enroll_year == int(scope["enroll_year"]))
    students = list(db.scalars(stmt))
    if not students:
        return {"students": 0, "created": 0}

    result = generate_batch(db, students, semester=scope.get("semester"))

    dispatched = sent = failed = 0
    if cfg.get("auto_dispatch"):
        for w in db.scalars(select(Warning).where(
            Warning.semester == result["semester"],
            Warning.student_id.in_([s.id for s in students]),
        )):
            s = dispatch_warning(db, w, channels=cfg.get("channels"))
            dispatched += 1
            sent += s.succeeded
            failed += s.failed
        result["dispatched"] = {"warnings": dispatched, "succeeded": sent, "failed": failed}

    return result

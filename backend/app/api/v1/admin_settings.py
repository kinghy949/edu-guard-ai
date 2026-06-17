from typing import Any

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_admin
from app.core.scheduler import run_with_lock, scheduler
from app.models.system import JobRun
from app.services.audit import record_audit
from app.services.jobs import (
    SETTING_KEY,
    get_warning_schedule,
    job_generate_warnings,
    set_warning_schedule,
)

router = APIRouter(dependencies=[Depends(require_admin)])

_JOB_ID = "warning_schedule"


class WarningScheduleConfig(BaseModel):
    enabled: bool = False
    cron: str = Field("0 3 * * 1", description="五段 cron 表达式：分 时 日 月 周")
    scope: dict[str, Any] = Field(default_factory=dict, description="可选键：college/major/enroll_year/semester")
    auto_dispatch: bool = False
    channels: list[str] = Field(default_factory=lambda: ["inbox"])


def _parse_cron(expr: str) -> CronTrigger:
    parts = expr.strip().split()
    if len(parts) != 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cron 必须是 5 段：分 时 日 月 周")
    minute, hour, day, month, day_of_week = parts
    try:
        return CronTrigger(minute=minute, hour=hour, day=day, month=month,
                           day_of_week=day_of_week, timezone="Asia/Shanghai")
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"非法 cron: {e}") from e


def _reschedule(cfg: WarningScheduleConfig) -> None:
    if scheduler is None or not scheduler.running:
        return  # 测试或未启动
    try:
        scheduler.remove_job(_JOB_ID)
    except Exception:
        pass
    if cfg.enabled:
        scheduler.add_job(
            func=lambda: run_with_lock("warning_schedule", job_generate_warnings),
            trigger=_parse_cron(cfg.cron),
            id=_JOB_ID, replace_existing=True,
        )


@router.get("/settings/warning-schedule", response_model=WarningScheduleConfig, summary="读取定时预警配置")
def get_warning_schedule_api(db: DbSession):
    return WarningScheduleConfig(**get_warning_schedule(db))


@router.put("/settings/warning-schedule", response_model=WarningScheduleConfig, summary="更新定时预警配置")
def put_warning_schedule(payload: WarningScheduleConfig, db: DbSession, current: CurrentUser):
    if payload.enabled:
        _parse_cron(payload.cron)  # 422 fast fail
    set_warning_schedule(db, payload.model_dump(), updated_by=current.id)
    record_audit(
        db, user=current, action="settings.warning_schedule.update",
        resource_type="system_setting", resource_id=SETTING_KEY,
        detail=payload.model_dump(),
    )
    db.commit()
    _reschedule(payload)
    return payload


@router.get("/job-runs", summary="最近的任务运行记录")
def list_job_runs(db: DbSession, job_name: str | None = None, limit: int = Query(50, ge=1, le=200)):
    stmt = select(JobRun).order_by(JobRun.id.desc()).limit(limit)
    if job_name:
        stmt = select(JobRun).where(JobRun.job_name == job_name).order_by(JobRun.id.desc()).limit(limit)
    rows = db.scalars(stmt)
    return [
        {
            "id": r.id, "job_name": r.job_name, "status": r.status,
            "started_at": r.started_at, "finished_at": r.finished_at,
            "result": r.result, "error": r.error,
        }
        for r in rows
    ]


@router.post("/jobs/generate-warnings/run-now", summary="立即触发一次定时预警任务")
def run_warnings_now(current: CurrentUser, db: DbSession):
    out = run_with_lock("warning_schedule", job_generate_warnings)
    record_audit(
        db, user=current, action="jobs.warning_schedule.run_now",
        detail=out,
    )
    db.commit()
    return out

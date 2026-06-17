"""APScheduler 调度框架。

设计取舍：
- 千人规模无需 Celery；APScheduler BackgroundScheduler 随 FastAPI lifespan
  启动即可
- 生产保持单 uvicorn worker；run_with_lock() 借 PostgreSQL advisory lock
  做双保险，避免重启/并发场景下重复触发
- 任务结果落 job_runs 表，便于审计
"""
from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.system import JobRun

log = get_logger("scheduler")

# 全局 scheduler 实例；启动后由 FastAPI lifespan 持有
scheduler: BackgroundScheduler | None = None


def _started_in_test() -> bool:
    """单测环境（PYTEST_CURRENT_TEST）下不真正启动 scheduler，避免对外副作用。"""
    return os.getenv("PYTEST_CURRENT_TEST") is not None


def start_scheduler() -> BackgroundScheduler:
    """幂等启动；在测试环境下不真正 start。"""
    global scheduler
    if scheduler and scheduler.running:
        return scheduler
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    if not _started_in_test():
        scheduler.start()
        log.info("scheduler_started")
    return scheduler


def shutdown_scheduler() -> None:
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")
    scheduler = None


def run_with_lock(
    job_name: str,
    fn: Callable[..., dict[str, Any] | None],
    *,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """获取 advisory lock 后执行 fn；结果落 job_runs。

    advisory lock key 由 hashtext(job_name) 派生，确保同名 job 跨进程互斥。
    拿不到锁直接 skipped。

    session_factory 可注入（测试用），默认走全局 SessionLocal。
    """
    factory = session_factory or SessionLocal
    with factory() as db:
        # 先尝试拿锁
        got = db.execute(text("SELECT pg_try_advisory_lock(hashtext(:k))"), {"k": job_name}).scalar()
        run = JobRun(job_name=job_name, status="running")
        db.add(run)
        db.flush()
        if not got:
            run.status = "skipped"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            log.info("job_skipped", job=job_name, reason="advisory_lock_held")
            return {"status": "skipped"}

        try:
            log.info("job_start", job=job_name)
            result = fn(db) if _expects_db(fn) else fn()
            run.status = "success"
            run.result = result or {}
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            log.info("job_success", job=job_name, result=result)
            return {"status": "success", "result": result}
        except Exception as e:
            db.rollback()
            # 重新开启事务记录失败（避免业务回滚把 run 也一起回滚）
            err_run = JobRun(job_name=job_name, status="failed", error=str(e),
                             finished_at=datetime.now(timezone.utc))
            db.add(err_run)
            db.commit()
            log.exception("job_failed", job=job_name)
            return {"status": "failed", "error": str(e)}
        finally:
            db.execute(text("SELECT pg_advisory_unlock(hashtext(:k))"), {"k": job_name})
            db.commit()


def _expects_db(fn: Callable) -> bool:
    """根据签名判断 fn 是否需要 Session 参数。"""
    import inspect

    try:
        params = inspect.signature(fn).parameters
        return len(params) >= 1
    except (TypeError, ValueError):
        return False

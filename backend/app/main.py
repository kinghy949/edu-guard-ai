from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as api_v1_router
from app.core.config import ensure_production_safe, settings
from app.core.logging import setup_logging
from app.core.rate_limit import LoginRateLimitMiddleware
from app.core.request_logging import RequestLoggingMiddleware
from app.core.scheduler import shutdown_scheduler, start_scheduler

# 生产环境启动前先校验关键安全配置（弱密钥/默认值直接拒绝启动）
ensure_production_safe()
# 配置结构化日志（dev 控制台 / prod JSON）
setup_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动调度器；若已有定时预警配置且启用，则根据 cron 注册
    sched = start_scheduler()
    try:
        from apscheduler.triggers.interval import IntervalTrigger

        from app.api.v1.admin_settings import WarningScheduleConfig, _parse_cron
        from app.core.db import SessionLocal
        from app.core.scheduler import run_with_lock
        from app.models.system import SystemSetting
        from app.services.jobs import SETTING_KEY, job_deliver_notifications, job_generate_warnings

        with SessionLocal() as db:
            row = db.get(SystemSetting, SETTING_KEY)
            if row and row.value and row.value.get("enabled"):
                cfg = WarningScheduleConfig(**row.value)
                sched.add_job(
                    func=lambda: run_with_lock("warning_schedule", job_generate_warnings),
                    trigger=_parse_cron(cfg.cron),
                    id="warning_schedule", replace_existing=True,
                )
        # 通知 outbox 消费：每 30 秒一次
        sched.add_job(
            func=lambda: run_with_lock("notify_deliver", job_deliver_notifications),
            trigger=IntervalTrigger(seconds=30),
            id="notify_deliver", replace_existing=True,
        )
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(title="EduGuard-AI", version="0.1.0", lifespan=lifespan)

# 中间件按"先注册后执行"顺序应用，CORS 应在最外层
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 登录接口 IP 级限流，防止暴力破解扫密
app.add_middleware(LoginRateLimitMiddleware)
# 请求日志 + request_id；放最内层以便贴近真实业务
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}

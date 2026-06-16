from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as api_v1_router
from app.core.config import ensure_production_safe, settings

# 生产环境启动前先校验关键安全配置（弱密钥/默认值直接拒绝启动）
ensure_production_safe()

app = FastAPI(title="EduGuard-AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}

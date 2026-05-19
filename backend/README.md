# EduGuard-AI Backend

FastAPI 后端服务。

## 启动

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload
```

打开 http://localhost:8000/docs 查看接口文档。

# EduGuard-AI Backend

FastAPI 后端服务。

## 启动

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env

# 初始化数据库（需先起好 PostgreSQL）
alembic upgrade head

# 创建初始管理员
python -m scripts.create_admin admin admin123 admin@example.com

# 启动
uvicorn app.main:app --reload
```

打开 http://localhost:8000/docs 查看接口文档。

## 鉴权流程

1. `POST /api/v1/auth/login`（OAuth2 表单：username/password）→ 返回 `access_token`。
2. 后续请求头 `Authorization: Bearer <token>`。
3. `GET /api/v1/auth/me` 查看当前用户。

## 角色

| 角色 | 说明 |
| --- | --- |
| `admin` | 系统管理员：用户、培养方案、配置 |
| `counselor` | 辅导员/班主任：学生、成绩、课程 |
| `student` | 学生：只能查看自己的资料、成绩、预警 |

## 主要接口

- `auth/`：register（管理员）、login、me
- `users/`：用户管理（管理员）
- `students/`：学生 CRUD（教职工）、`/me` 查看本人（学生）
- `programs/`：培养方案 + 学分桶 + 课程映射
- `courses/`：课程主数据
- `grades/`：成绩录入与查询（学生只能看自己）

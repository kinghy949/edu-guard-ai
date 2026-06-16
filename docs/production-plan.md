# EduGuard-AI 大学落地版完善规划

## Context

EduGuard-AI 是一套高校学业预警系统（FastAPI + SQLAlchemy 2 + Alembic / Vue3 + Element Plus / PostgreSQL 15 / docker-compose 部署），核心链路已成型：教务数据 CSV/Excel 导入 → 学分比对（`credit_compare.py`）→ 三级预警（`warning_engine.py`）→ 多渠道通知（`notify_dispatcher.py`）→ AI 学业问答（OpenAI 兼容 + SSE 流式），三角色权限（student/counselor/admin）。

但目前是 demo 级，距离大学真实试点有明显差距：**零测试、零日志、零审计、CORS 全开（`main.py:10` allow_origins=["*"]）、LLM api_key 与 SMTP 密码明文落库、学生初始密码=学号且无强制改密、无登录限流、通知同步发送会阻塞、预警规则硬编码、无定时任务、无 CI、无备份方案**。

本规划目标：将系统完善为**单院系（千人内）可真实试点使用的版本**，交付给 Codex 按任务逐个开发。

**用户已确认的方向**：
- 认证：保持本地账号体系（不做 CAS/SSO），但补齐账号安全
- 数据：以增强 CSV/Excel 导入为主（映射模板、dry-run、错误报告、历史回滚），不对接教务 API
- 规模：千人级单机部署，避免重型基础设施
- 新功能：辅导员工作台增强 + 报表导出 + 学生端体验增强，三者都要

## 全局技术决策（所有任务前提）

| 领域 | 决策 | 理由 |
|---|---|---|
| 定时任务 | APScheduler（BackgroundScheduler，随 FastAPI lifespan 启动）+ PG advisory lock 防重 | 千人规模无需 Celery；生产保持单 uvicorn worker，文档注明 |
| 通知异步 | Outbox 模式：`notifications` 表即队列（status=pending），APScheduler 周期消费 + 指数退避重试 | 复用现有表，无新中间件 |
| 敏感配置加密 | `cryptography` Fernet，密文带 `enc:v1:` 前缀，兼容存量明文 | api_key/SMTP 密码当前明文存 DB |
| 结构化日志 | structlog（dev 彩色控制台 / prod JSON），中间件注入 request_id | |
| Excel 导出 | openpyxl（已在依赖中） | 无新依赖 |
| PDF 报表 | 不引服务端 PDF 库，前端 `@media print` 打印样式 + 浏览器"打印为 PDF" | 成本/收益 |
| 测试 | pytest + 真实 PostgreSQL 测试库（模型用了 JSONB，不能 SQLite）+ TestClient 依赖覆盖 | |
| 迁移 | Alembic 从 `0003` 起按任务编号，每个含 DDL 的任务独立迁移 | 现有 0001/0002 |
| 新增依赖 | `backend/pyproject.toml`：apscheduler>=3.10、cryptography>=42、structlog>=24；dev extras：pytest、pytest-cov、ruff | |

通用约定：后端复用 `app/api/deps.py` 的 `require_staff`/`require_admin`；业务逻辑放 `backend/app/services/`；前端 API 统一加 `frontend/src/api/endpoints.ts`，新页面注册 `frontend/src/router/index.ts` 与 `Layout.vue` 菜单。

---

## 阶段一：工程与安全基线（最先做，后续任务依赖测试与审计设施）

### T1.1 pytest 基础设施 + 核心服务单测
**目的**：建立测试地基，保护后续重构。
**设计**：
- 新建 `backend/tests/conftest.py`：
  - 读 `TEST_DATABASE_URL` 环境变量（默认 `postgresql+psycopg://eduguard:eduguard@localhost:5432/eduguard_test`）；session 级 create_all/drop_all（基于 `app.core.db.Base.metadata`）；function 级事务回滚 `db` fixture（嵌套事务 + rollback）。
  - `client` fixture：TestClient(app)，override `get_db`。
  - 工厂 helper：`make_user(role)`、`make_student(...)`、`make_program_with_buckets(...)`、`make_grade(...)`、`auth_header(user)`（直接调 `create_access_token`）。
- 新建测试：
  - `tests/services/test_credit_compare.py`：无方案学生、空桶、已修/在修/挂科/重修计入逻辑、缺口计算、推荐课排除已修。
  - `tests/services/test_warning_engine.py`：三档分级各条件分支（挂科→severe、必修<0.5、总缺口、warn 两条件、info、达标返回 None）、`estimated_stage` 边界（入学当年、超 8 学期封顶）。
  - `tests/services/test_importer.py`：四个 import 函数的 created/updated/错误行各路径；学生重复导入只 update 不重建用户。
- `pyproject.toml` 加 `[project.optional-dependencies] dev` 与 `[tool.pytest.ini_options]`。
**验收**：`cd backend && pytest` 全绿；三个 service 覆盖率 ≥ 85%；只写 eduguard_test 库。

### T1.2 API 集成测试 + 权限矩阵
**设计**：
- `tests/api/test_auth.py`：登录成功/密码错/停用账户；`/auth/me`。
- `tests/api/test_permissions.py`：参数化权限矩阵——对代表性端点（`POST /imports/students`、`POST /warnings/generate`、`PUT /notifications/configs/email`、LLM 配置、`GET /students`、`GET /warnings`、`GET /progress/{id}`）断言 student/counselor/admin/匿名 的 200/401/403。
- `tests/api/test_warnings_api.py`：学生只能看自己的预警；generate 全流程。
- `tests/api/test_imports_api.py`：合法 CSV（io.BytesIO multipart）返回 created 数；全错文件回滚。
**验收**：权限矩阵 ≥ 25 条用例通过；`pytest --cov=app` 总覆盖率 ≥ 60%。

### T1.3 CORS 白名单与 SECRET_KEY 治理
**设计**：
- `backend/app/core/config.py`：加 `CORS_ORIGINS: list[str] = ["http://localhost:5173"]`、`ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440`。
- `backend/app/main.py`：CORS 改读 settings；启动校验——`APP_ENV == "prod"` 且（SECRET_KEY == "change-me" 或 len < 32）时 raise RuntimeError 拒绝启动。
- `security.py` 的过期时间改读 settings。
- 完善 `backend/.env.example`（全部配置项+注释）；`docs/deploy.md` 加 `openssl rand -hex 32` 说明。
**验收**：响应头不再对任意 Origin 放行；prod + 默认密钥启动报错（单测）；.env.example 完整。

### T1.4 密码策略 + 强制首次改密
**设计**：
- 迁移 `0003_user_security.py`：users 加 `must_change_password BOOL DEFAULT false`、`password_updated_at`、`failed_login_count INT DEFAULT 0`、`locked_until`（后两列供 T1.5，合并迁移）。`models/user.py` 同步。
- 新建 `backend/app/core/password_policy.py`：`validate_password(pw)`——长度≥8、含字母和数字、不等于用户名/学号，返回错误列表。
- `api/v1/auth.py`：新增 `POST /auth/change-password`（校验旧密码+策略，更新 hash、must_change_password=False）；登录响应 TokenRead 加 `must_change_password` 字段；register 走策略校验。
- `importer.py` 的 import_students 新建用户置 `must_change_password=True`；`scripts/bootstrap.py` 同理。
- 前端：新建 `ChangePassword.vue`（路由 /change-password）；user store 保存 mustChangePassword；路由守卫强制重定向；Layout.vue 加"修改密码"菜单。
**验收**：新学生首次登录被强制跳改密页；弱密码 400 并返回原因；改密后旧密码失效（API 测试）。

### T1.5 登录失败锁定与限流
**设计**：
- `auth.py` login 改造：`locked_until > now` → 423（返回剩余分钟）；密码错 `failed_login_count += 1`，达 5 次锁 15 分钟并清零；统一文案"用户名或密码错误"不泄露用户存在性；成功登录清零。配置 `LOGIN_MAX_FAILED=5`、`LOGIN_LOCK_MINUTES=15` 入 config.py。
- IP 兜底：main.py 加轻量内存限流中间件（仅 /auth/login，每 IP 每分钟 ≤10 次，超 429）；单 worker 下内存实现足够，注释说明约束。
**验收**：5 次错密后第 6 次 423；锁定期正确密码也 423；成功登录重置；单测覆盖三路径。

### T1.6 敏感配置加密存储
**设计**：
- 新建 `backend/app/core/crypto.py`：`encrypt_str → "enc:v1:<fernet>"`、`decrypt_str`（无前缀视为明文返回，兼容存量）、`mask`（保留末 4 位）。密钥：新配置 `ENCRYPTION_KEY`；为空时从 SECRET_KEY PBKDF2 派生（dev 便利），prod 校验要求显式设置（并入 T1.3 校验）。
- `api/v1/llm_config.py`：写入加密；读取返回 mask；update 收到含 `*` 的掩码值则保留原 key。`ai/config_loader.py` 读取时解密。
- `api/v1/notifications.py` + `notify_dispatcher.py`：定义 `SENSITIVE_KEYS = {"email": ["password"], "sms": ["access_key_secret"], "wecom": ["webhook"], "dingtalk": ["webhook", "secret"]}`；upsert 前对敏感键加密、掩码跳过；GET 返回掩码；发送侧解密后交 notifier。
- 前端 Admin.vue：密钥输入框 placeholder 提示"留空保持不变"。
**验收**：查库确认密文前缀 `enc:v1:`；GET 无明文；LLM 测试连接与邮件测试发送仍正常；存量明文无需迁移可继续用。

### T1.7 结构化日志 + 请求日志中间件
**设计**：
- 新建 `backend/app/core/logging.py`：`setup_logging()`——structlog（dev ConsoleRenderer / prod JSONRenderer，按 APP_ENV），接管 uvicorn logger 级别；main.py 加载时调用。
- main.py 中间件：每请求生成/透传 `X-Request-ID`，bind 到 structlog contextvars；完成时记 `http_request` 日志（method/path/status/duration_ms/user_id/client_ip）；响应头回写；未捕获异常记 exc_info。
- service 关键点补日志：导入开始/结束、预警批量生成、通知失败、LLM 调用异常。
**验收**：任意 API 输出含 request_id/duration 的结构化日志；prod 单行 JSON；500 有带堆栈的错误日志。

### T1.8 操作审计
**设计**：
- 迁移 `0004_audit_logs.py`：`audit_logs(id, user_id FK SET NULL, username, action VARCHAR(64), resource_type, resource_id, detail JSONB, ip, created_at)`，索引 `(action, created_at)`、`(user_id, created_at)`。
- 新建 `models/audit.py`、`services/audit.py`：`record_audit(db, *, user, action, ...)`（只 db.add，跟随调用方事务）。
- 埋点：login 成功/失败/锁定、change-password、imports.*（文件名+结果计数）、notifications.upsert_config、llm_config.update、warnings.generate/resolve、users.register。action 命名 `资源.动作`。
- 新建 `api/v1/audit.py`：`GET /admin/audit-logs`（admin only，过滤 action/user_id/时间，分页 `{items, total}`）。
- 前端 Admin.vue 加"审计日志" tab（表格+过滤+分页）。
**验收**：导入与改密后审计可查（含操作者/IP/摘要）；登录失败留痕；学生访问 403。

### T1.9 GitHub Actions CI
**设计**：
- 新建 `.github/workflows/ci.yml`：job backend（Python 3.11 + postgres:15 service，`pip install -e .[dev]`，`ruff check`，`pytest --cov=app --cov-fail-under=60`）；job frontend（Node 20，npm ci，`vue-tsc --noEmit`（无脚本则补），npm run build）。
- pyproject 加 `[tool.ruff]`（line-length 120, select E/F/I），修复存量 lint 问题（如 warning_engine.py 未使用 import）。
**验收**：push 后两 job 全绿；引入错误时 CI 变红。

---

## 阶段二：导入增强与预警/通知引擎升级

### T2.1 导入批次模型与历史
**设计**：
- 迁移 `0005_import_batches.py`：
  - `import_batches(id, kind, filename, status DEFAULT 'completed' -- completed/failed/rolled_back/dry_run, dry_run BOOL, total_rows, created_count, updated_count, skipped_count, error_count, errors JSONB, mapping JSONB, operator_id FK, created_at, updated_at)`
  - `import_batch_rows(id, batch_id FK CASCADE, row_no, op -- create/update, table_name, record_pk, before JSONB)`，索引 (batch_id)。
- 新建 `models/import_batch.py`、`schemas/import_batch.py`。
- 重构 `services/importer.py`：`ImportResult` 加 `rows: list[RowChange]`；四个 import_* 在 create/update 时登记 RowChange（update 前抓变更字段旧值快照）。新增统一入口 `run_import(db, kind, df, *, operator_id, filename, mapping=None, dry_run=False) -> ImportBatch`：dry_run 用 savepoint 执行后回滚数据写入、保留 batch 记录。
- `api/v1/imports.py`：四端点改走 run_import；新增 `GET /imports/batches`（staff，分页+kind 过滤）、`GET /imports/batches/{id}`（含 errors）。审计带 batch_id。
- 前端 Admin.vue 导入 tab 下加"导入历史"表格。
**验收**：每次导入产生批次+行级快照；原导入行为不回归（T1 测试过）；单测覆盖 run_import 快照内容。

### T2.2 dry-run 预检与错误报告下载
**设计**：
- 上传端点加 query `dry_run: bool = False`；dry_run 返回 `{batch_id, would_create, would_update, errors: [{row, message}], sample: 前5行}`，业务数据零变化。
- `GET /imports/batches/{id}/errors.xlsx`：openpyxl 生成（行号/错误信息），StreamingResponse。
- 前端导入区改造：上传后默认先 dry-run，弹预检结果对话框（计数+错误明细+下载按钮），确认后以 dry_run=false 真正提交。
**验收**：含错文件 dry-run 后 students 行数不变；确认后落库；错误 Excel 行号与文件一致。

### T2.3 字段映射模板
**设计**：
- 迁移 `0006_import_mappings.py`：`import_mappings(id, kind, name, mapping JSONB -- {"源列名":"目标字段"}, is_default, created_by, created_at, updated_at)`，唯一 (kind, name)。
- importer.py：parse_table 后 `apply_mapping(df, mapping)`（重命名列、丢未映射列）；run_import 接受 mapping_id 或内联 mapping。
- API：`GET/POST/PUT/DELETE /imports/mappings`（staff）；上传端点加 form 字段 mapping_id/mapping。
- 前端：上传组件加映射选择器 + 映射编辑对话框（左列=dry-run 返回的实际表头，右列=目标字段下拉），可存为模板。
**验收**：中文表头 CSV 通过映射成功导入；模板 CRUD 正常；无映射时英文表头行为不变。

### T2.4 导入回滚
**设计**：
- 新建 `services/import_rollback.py`：`rollback_batch(db, batch_id, operator_id)`——校验 status=completed；同 kind 存在后续批次时 409 拒绝；按 import_batch_rows 倒序：create→删除（学生级联删 User；已有成绩/预警则跳过计入 skipped_details）、update→回写 before 快照；置 status='rolled_back'，审计 `imports.rollback`。
- API：`POST /imports/batches/{id}/rollback`（admin only），返回 `{restored, deleted, skipped, skipped_details}`。
- 前端导入历史加"回滚"按钮（admin，二次确认）。
**验收**：导入成绩→回滚→grades 字段级恢复（单测）；有后续批次时 409；不可重复回滚。

### T2.5 预警规则配置化
**设计**：
- 迁移 `0007_warning_rules.py`：`warning_rules(id, name, scope_college NULL, scope_major NULL, severe_total_gap_ratio DEFAULT 0.5, warn_total_gap_ratio DEFAULT 0.25, severe_required_ratio DEFAULT 0.5, warn_category_ratio DEFAULT 0.7, required_category_keywords JSONB DEFAULT '["必修"]', stage_total_semesters DEFAULT 8, enabled, priority, updated_by, ...)`；迁移内插入全局默认规则。
- 新建 model + schema（阈值 0~1、semesters 1~16 校验）。
- `warning_engine.py`：`load_rule_for_student(db, student)`——enabled 规则中 scope 匹配（major 精确 > college 精确 > 全局）且 priority 最高者，转现有 WarningRule dataclass；generate 默认 rule=None 时调用；Warning.detail 记 rule_id。
- 新建 `api/v1/warning_rules.py`：CRUD `/admin/warning-rules`（admin）；删除全局默认规则拒绝。
- 前端 Admin.vue 加"预警规则" tab（列表+编辑表单）。
**验收**：改阈值后重新生成预警分级随之变化（临界数据单测）；专业规则优先于全局；非法阈值 422。

### T2.6 预警处理流（状态机 + 跟进记录）
**设计**：
- 迁移 `0008_warning_workflow.py`：warnings 加 `status DEFAULT 'open'`（open/following/resolved/ignored）、`assignee_id FK NULL`；存量 resolved_at 非空记录置 resolved；索引 (status, level)。新表 `warning_actions(id, warning_id FK CASCADE, user_id FK SET NULL, action -- comment/follow/resolve/ignore/reopen, note TEXT, created_at)`。
- 新建 `services/warning_workflow.py`：`apply_action(db, warning, user, action, note)`——状态机：open→following/resolved/ignored；following→resolved/ignored；resolved/ignored→reopen→open；comment 任意状态不改 status；resolve 写 resolved_at 兼容旧字段；follow 置 assignee；非法流转 ValueError→409。
- API：`POST /warnings/{id}/actions`（staff）、`GET /warnings/{id}/actions`（staff；学生 403——跟进记录属内部工作流）；现有 `/resolve` 改内部调 apply_action 保持兼容；`GET /warnings` 加 status/assignee_id 过滤。审计 `warnings.action`。
**验收**：非法流转 409；每次操作有 action 记录；存量数据迁移后 status 正确；单测覆盖全部流转。

### T2.7 APScheduler 调度框架 + 定时自动预警
**设计**：
- 迁移 `0009_scheduler.py`：`system_settings(key PK, value JSONB, updated_by, updated_at)`，插入默认 `warning_schedule = {"enabled": false, "cron": "0 3 * * 1", "scope": {}, "auto_dispatch": false, "channels": ["inbox"]}`；`job_runs(id, job_name, started_at, finished_at, status, result JSONB, error)`。
- 新建 `core/scheduler.py`：BackgroundScheduler，挂 FastAPI lifespan（main.py 改 lifespan 写法）；`run_with_lock(job_name, fn)`——`pg_try_advisory_lock(hashtext(job_name))` 拿不到锁跳过，结果落 job_runs。
- 新建 `services/jobs.py`：`job_generate_warnings()`——读 settings，enabled 才执行，按 scope 调 generate_batch，auto_dispatch 时入队通知（T2.8）。
- 新建 `api/v1/admin_settings.py`：`GET/PUT /admin/settings/warning-schedule`（PUT 校验 cron 并 reschedule）、`GET /admin/job-runs`、`POST /admin/jobs/generate-warnings/run-now`。
- 前端 Admin.vue 批量预警 tab 加定时配置区（开关、周几+时间下拉、自动通知开关）+ 运行记录表。
- `docs/operations.md` 注明生产单 uvicorn worker（advisory lock 双保险）。
**验收**：run-now 后 job_runs 出现 success 且预警生成；两连接并发仅一个执行；非法 cron 422。

### T2.8 通知异步化（Outbox + 重试）
**设计**：
- 迁移 `0010_notification_outbox.py`：notifications 加 `subject`、`content TEXT`、`retry_count DEFAULT 0`、`next_attempt_at`、`read_at`（read_at 供 T4.2）；索引 (status, next_attempt_at)。
- 重构 `notify_dispatcher.py`：
  - `dispatch()` 改入队：每渠道写 pending 记录立即返回（收件人缺失/渠道未启用直接 failed 不重试）；inbox 渠道直接 sent。
  - 新增 `deliver_pending(db, limit=50)`：`status='pending' AND next_attempt_at<=now` + `FOR UPDATE SKIP LOCKED`，逐条发送；失败 retry_count+1，≥3 置 failed，否则 next_attempt_at = now + [1,5,30]min 退避。
- `services/jobs.py` 注册 `job_deliver_notifications`，IntervalTrigger 30s，走 run_with_lock。
- API：`POST /notifications/{id}/resend`（staff，重置 pending）；`/notifications/test` 保持同步直发。
- warnings.py 的 auto_dispatch 改入队，响应 `{"queued": N}`。
**验收**：批量 100 条预警+通知的 API 响应 <2s；错误 SMTP 经 3 次重试转 failed 且间隔符合退避（断言 next_attempt_at）；resend 重投；inbox 即时可见。

### T2.9 SMS Notifier 接口规范化
**设计**：
- `notifiers/sms.py`：config 加 `provider`（mock | aliyun）；mock 记日志返回 ok（payload 标 mock=true）；aliyun 用 httpx 实现阿里云 SMS V3 HMAC-SHA256 签名调用（不引阿里 SDK），单测 mock httpx。
- `notifiers/base.py` 加 `validate_config(config) -> list[str]` 协议方法，各 notifier 实现；保存配置前校验。
- 更新 `docs/notifications.md`。
**验收**：mock 测试发送 ok；缺字段保存 400 提示具体缺项；aliyun 分支单测验证签名头与请求体。

---

## 阶段三：辅导员工作台与报表

### T3.1 学业进度快照 + 统计大盘 API
**设计**：
- 迁移 `0011_progress_snapshots.py`：`student_progress_snapshots(student_id PK FK CASCADE, total_required, total_earned, total_in_progress, total_gap NUMERIC(6,1), completion_ratio FLOAT, failed_count INT, computed_at)`。
- 新建 `services/stats.py`：
  - `refresh_snapshots(db, student_ids=None)`：调 compute_student_progress 逐人 upsert（千人 <1 分钟）。触发：成绩/方案导入成功后增量刷新受影响学生、预警定时任务前、手动 API。
  - `overview(db, college=None)`、`warning_trend(db, semesters=6)`（按 warnings.semester 分组）、`class_ranking(db, ...)`（按 class_name：人数/平均完成度/open 预警/severe 数）、`level_distribution(db, dim)`（dim ∈ college/major/class_name）。
- 新建 `api/v1/stats.py`（require_staff）：`GET /stats/overview`、`/stats/warning-trend`、`/stats/class-ranking`、`/stats/distribution?dim=`、`POST /stats/refresh-snapshots`。
**验收**：3 班级数据 ranking 与手算一致（单测）；导入成绩后快照自动更新；学生 403。

### T3.2 辅导员统计大盘页面
**设计**：
- 前端加 `echarts`（按需引入）。
- 新建 `views/CounselorDashboard.vue`：指标卡（学生数/未处理预警分级/平均完成度/挂科人数）、预警趋势折线、班级完成度排名条形图（点击跳学生列表带筛选）、分布饼图、刷新快照按钮。
- 路由 `/workbench`（staff）；登录后默认跳转：student → /dashboard，staff → /workbench。
**验收**：counselor 看到真实数据图表；学生访问被重定向；班级点击跳转携带 query。

### T3.3 学生列表高级筛选与分页
**设计**：
- `api/v1/students.py` 改造 `GET /students`：参数 page/size/keyword（学号姓名模糊）/college/major/class_name/enroll_year/has_open_warning/warning_level/completion_lt（join 快照）/sort；响应 `{items, total}`，item = StudentRead + completion_ratio + open_warning_level（最高未处理级别子查询）。
- 新建 `views/Students.vue`：筛选栏+表格（完成度进度条、预警级别 tag、详情按钮）+分页；路由 `/students`（staff），菜单"学生管理"。
**验收**：组合筛选结果正确（API 测试）；total 与分页一致；空快照学生 completion 为 null 不报错。

### T3.4 学生 360 详情页
**设计**：
- 后端 `students.py` 加 `GET /students/{id}/transcript`（staff 或本人）：按学期分组成绩单（join courses）。
- 新建 `views/StudentDetail.vue`（路由 `/students/:id`，staff）：基本信息卡（完成度环形图，复用 /progress/{id}）、学分桶进度条、成绩单（按学期折叠，挂科红色）、预警历史时间线（含状态 tag、跟进记录、可直接发起 action）。
**验收**：四区块数据完整；挂科红色；详情页执行"跟进"后时间线即时刷新；学生访问他人 403。

### T3.5 预警处理流前端
**设计**：
- 改造 `views/Warnings.vue`：staff 视图加状态列/负责人列/status 筛选；行操作"处理"打开 Drawer——详情+跟进时间线+操作区（动作下拉+备注+提交）。学生视图仅展示自己预警与状态。
- endpoints.ts 加 warningsApi.actions / applyAction；Warning 类型加 status/assignee_id。
**验收**：counselor 在抽屉完成 open→following→resolved 全流程，列表实时更新；后端 409 时前端有提示；时间线倒序显示操作人与备注。

### T3.6 Excel 导出服务与报表 API
**设计**：
- 新建 `services/exporter.py`：openpyxl 通用 `build_workbook(sheets)`（标题行加粗冻结、列宽自适应）。
- 新建 `api/v1/reports.py`（require_staff）：
  - `GET /reports/warnings.xlsx?semester&level&status&college&class_name`：预警明细。
  - `GET /reports/completion.xlsx?college&enroll_year&class_name`：完成度（来自快照+学生表）。
  - `GET /reports/class-summary.xlsx`：班级汇总（复用 T3.1 ranking）。
  - StreamingResponse，文件名含日期；审计 `reports.export`。
**验收**：xlsx 可打开、表头中文、行数与筛选一致（测试用 openpyxl 重读断言）；千人导出 <5s；学生 403。

### T3.7 报表中心页面 + 打印（PDF 替代）
**设计**：
- 新建 `views/Reports.vue`（路由 /reports，staff）：三类报表卡片，筛选表单 + Excel 下载（axios blob）+ 打印视图按钮。
- 新建 `views/ReportPrint.vue`（路由 /reports/print?type=&filters=）：纯展示页 + `@media print` 样式（隐藏导航、A4 边距、`break-inside: avoid`），按钮调 window.print()。
**验收**：Excel 下载正确；Chrome 打印预览无导航、表格完整分页；筛选条件回显页眉。

---

## 阶段四：学生端体验、AI 增强与运维交付

### T4.1 学业地图
**设计**：
- `services/credit_compare.py` 加 `build_academic_map(db, student)`：按学分桶分组 program_courses，每门课标状态——completed/in_progress/failed（最新 FAILED 且无后续通过）/retake/not_taken，附 score、semester_suggested。新端点 `GET /progress/me/map`、`GET /progress/{id}/map`（staff）。
- 新建 `views/AcademicMap.vue`（路由 /map，学生菜单"学业地图"）：按桶分区课程卡片网格（绿=已修/蓝=在修/红=挂科/灰=未修），桶头部进度条+缺口提示，"修读建议"侧栏（复用 recommended，按建议学期排序）。
**验收**：状态着色正确（单测覆盖 5 种状态，含挂科后重修通过显示 completed）；缺口桶高亮展示推荐课；无方案学生显示友好空态。

### T4.2 消息中心（站内信）
**设计**：
- 复用 T2.8 的 read_at/subject/content 列。
- API：`GET /notifications/me?unread_only&page&size`（inbox 渠道，返回 `{items, total, unread_count}`）、`POST /notifications/{id}/read`、`POST /notifications/me/read-all`。
- 前端：Layout.vue 顶栏铃铛+未读角标（60s 轮询）；新建 `views/Messages.vue`（路由 /messages）：列表（未读加粗）、点击展开标记已读、全部已读；预警消息附跳转。
**验收**：预警 inbox 分发后铃铛出现未读数；阅读后角标减少、read_at 落库；只能操作本人消息（403 测试）。

### T4.3 AI 上下文 token 截断
**设计**：
- 新建 `backend/app/ai/budget.py`：`estimate_tokens(text) ≈ len(text)//2 + 1`（中文经验值，不引 tiktoken）；`fit_messages(messages, max_tokens)`：保 system 与最后一条 user，历史从最旧丢弃，超长单条截尾加"…(已截断)"。
- config.py 加 `LLM_MAX_CONTEXT_TOKENS: int = 6000`；`api/v1/chat.py` 的 _build_messages 末尾调用。
**验收**：50 条长历史后 messages 估算 ≤ 上限（单测）；system 与最新输入永不被丢弃；短对话行为不变。

### T4.4 AI 对话限额与免责声明
**设计**：
- config.py 加 `CHAT_DAILY_MESSAGE_LIMIT: int = 50`（0=不限）。
- chat.py：发送前统计当前用户今日 user 消息数（join chat_sessions），超限 429；stream/非 stream 都加。新端点 `GET /chat/quota` 返回 `{limit, used, remaining}`。
- prompts.py SYSTEM_PROMPT 追加"回答仅供参考，以教务处文件为准"；Chat.vue 输入框下灰字声明 + AI 回复底部小字"AI 生成，仅供参考"。
**验收**：limit=2 时第 3 条 429（API 测试）；quota 跨 session 累计、不计 assistant 消息；前端两处声明可见。

### T4.5 敏感信息脱敏显示
**设计**：
- 新建 `frontend/src/utils/mask.ts`：maskPhone（138****1234）、maskEmail（a**@x.com）。应用于学生列表、Admin 用户展示；学生详情页对 staff 提供"点击显示"完整信息。
- `docs/deploy.md` 加 nginx HTTPS（certbot）配置与 80→443 跳转；`docs/operations.md` 加数据合规清单（最小化采集、账号回收、导出文件管理）。
**验收**：列表脱敏渲染；部署文档含可执行的 HTTPS 步骤。

### T4.6 数据库备份与恢复
**设计**：
- 新建 `scripts/db_backup.sh`：`pg_dump -Fc` 到 `backups/eduguard_YYYYmmdd_HHMM.dump`，保留最近 14 份；`scripts/db_restore.sh <file>`（pg_restore --clean）。
- 推荐宿主 crontab 方案（`0 2 * * *`），写入 `docs/operations.md` 含恢复演练步骤。
**验收**：备份脚本生成 dump；删数据后 restore 完整恢复；轮转保留 14 份。

### T4.7 健康检查与版本号
**设计**：
- main.py `/health` 增强：`{status, version, db: ok/error}`（SELECT 1 探测，db 失败整体 503）；版本单一来源 `backend/app/__init__.py` 的 `__version__`，pyproject 用 dynamic version，FastAPI version 同源。
- docker-compose.prod.yml backend 加 healthcheck（curl /health）。
- 前端 Layout.vue 页脚显示版本（vite.config.ts 构建期注入 package.json version）。
**验收**：停 DB 后 /health 503；compose ps 显示 healthy；版本号只改一处。

### T4.8 部署与运维文档收口
**设计**：更新 `docs/deploy.md`、`docs/operations.md`、`README.md`：
- 完整 .env 清单（SECRET_KEY/ENCRYPTION_KEY/CORS_ORIGINS/限额等新变量）与生成方法。
- 首次上线 checklist：改 admin 密码→配 LLM/SMTP→导入流程（映射→dry-run→确认）→配预警规则与定时→备份 crontab。
- 单 worker 约束、升级流程（备份→pull→alembic upgrade→重启）、回滚流程、故障排查（job_runs/audit_logs/request_id 串联）。
**验收**：按文档可从零完成部署演练；文档环境变量与 config.py 一致无遗漏。

---

## 实施顺序与依赖

```
阶段一：T1.1→T1.2 先行；T1.3~T1.8 可并行；T1.9 收尾
阶段二：T2.1→T2.2→T2.3→T2.4 串行；T2.5→T2.6 串行；T2.7→T2.8 串行；T2.9 独立
阶段三：T3.1 先行（T3.2/T3.3/T3.6 依赖它）；T3.4 依赖 T3.3+T2.6；T3.5 依赖 T2.6；T3.7 依赖 T3.6
阶段四：T4.2 依赖 T2.8 迁移；其余可与阶段三并行
```

## 统一 Definition of Done（每个任务）

- 相关 pytest 通过且 CI 绿
- 含 DDL 的任务有可 upgrade/downgrade 的 alembic 迁移
- 新 API 出现在 OpenAPI 文档（/docs）
- 涉及前端的任务 vue-tsc 与 build 通过
- 关键操作有审计埋点（T1.8 之后的任务）

## 关键改造文件

- `backend/app/services/warning_engine.py` — 规则配置化、状态机核心改造点
- `backend/app/services/notify_dispatcher.py` — 同步发送改 outbox 异步
- `backend/app/services/importer.py` — dry-run/映射/批次快照/回滚载体
- `backend/app/api/v1/auth.py` — 密码策略、强制改密、登录锁定
- `backend/app/core/config.py` + `main.py` — 新配置汇聚、CORS/lifespan/中间件改造

## 验证方式

- 后端：`cd backend && pytest --cov=app`（需本地 PostgreSQL 测试库）
- 前端：`cd frontend && npm run build` + vue-tsc
- 端到端：docker compose up 后按各任务验收标准人工核验（导入 dry-run 流程、预警状态流转、消息中心、报表下载、打印视图）
- CI：push 后 GitHub Actions 两 job 全绿

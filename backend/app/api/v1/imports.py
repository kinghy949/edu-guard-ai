import io
import json

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_staff
from app.core.logging import get_logger
from app.models.import_batch import ImportBatch
from app.models.import_mapping import ImportMapping
from app.schemas.import_batch import ImportBatchDetail, ImportBatchPage, ImportBatchSummary
from app.schemas.import_mapping import ImportMappingCreate, ImportMappingRead, ImportMappingUpdate
from app.services import importer
from app.services.audit import record_audit

router = APIRouter(dependencies=[Depends(require_staff)])
log = get_logger("imports")


async def _read(file: UploadFile) -> bytes:
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "缺少文件名")
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件为空")
    return data


def _resolve_mapping(db, kind: str, mapping_id: int | None, mapping_json: str | None) -> dict[str, str] | None:
    if mapping_id:
        m = db.get(ImportMapping, mapping_id)
        if not m or m.kind != kind:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "映射模板不存在或类型不匹配")
        return m.mapping
    if mapping_json:
        try:
            data = json.loads(mapping_json)
        except json.JSONDecodeError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"mapping JSON 解析失败: {e}") from e
        if not isinstance(data, dict):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "mapping 必须是 {源列名: 目标字段} 字典")
        return {str(k): str(v) for k, v in data.items()}
    return None


def _run(*, db, data: bytes, filename: str, kind: str, user, request, dry_run: bool = False,
         mapping: dict[str, str] | None = None):
    """所有 import_* 端点的统一路径：解析 → run_import → 审计 → 返回汇总。"""
    try:
        df = importer.parse_table(data, filename)
    except ValueError as e:
        log.warning("import_parse_error", kind=kind, filename=filename, error=str(e))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    try:
        batch = importer.run_import(
            db, kind=kind, df=df, operator_id=user.id if user else None,
            filename=filename, dry_run=dry_run, mapping=mapping,
        )
    except Exception:
        db.rollback()
        log.exception("import_exception", kind=kind, filename=filename)
        raise
    record_audit(
        db, user=user, action=f"imports.{kind}",
        resource_type="import_batch", resource_id=batch.id,
        detail={
            "filename": filename,
            "status": batch.status,
            "dry_run": dry_run,
            "created": batch.created_count,
            "updated": batch.updated_count,
            "skipped": batch.skipped_count,
            "error_count": batch.error_count,
        },
        request=request,
    )
    db.commit()
    db.refresh(batch)
    resp = {
        "batch_id": batch.id,
        "status": batch.status,
        "dry_run": batch.dry_run,
        "created": batch.created_count,
        "updated": batch.updated_count,
        "skipped": batch.skipped_count,
        "errors": batch.errors or [],
    }
    if dry_run:
        # 给前端预检对话框提供"将创建/将更新"语义化字段
        resp["would_create"] = batch.created_count
        resp["would_update"] = batch.updated_count
    return resp


@router.post("/students", summary="导入学生名册")
async def import_students(
    db: DbSession, file: UploadFile, current: CurrentUser, request: Request,
    dry_run: bool = Query(False, description="预检模式：不落库，仅返回将要发生的变更与错误"),
    mapping_id: int | None = Form(None),
    mapping: str | None = Form(None, description='{源列名: 目标字段} JSON 字符串'),
):
    data = await _read(file)
    m = _resolve_mapping(db, "students", mapping_id, mapping)
    return _run(db=db, data=data, filename=file.filename, kind="students", user=current,
                request=request, dry_run=dry_run, mapping=m)


@router.post("/courses", summary="导入课程主数据")
async def import_courses(
    db: DbSession, file: UploadFile, current: CurrentUser, request: Request,
    dry_run: bool = Query(False),
    mapping_id: int | None = Form(None),
    mapping: str | None = Form(None),
):
    data = await _read(file)
    m = _resolve_mapping(db, "courses", mapping_id, mapping)
    return _run(db=db, data=data, filename=file.filename, kind="courses", user=current,
                request=request, dry_run=dry_run, mapping=m)


@router.post("/programs", summary="导入培养方案 + 学分桶 + 课程映射")
async def import_program(
    db: DbSession, file: UploadFile, current: CurrentUser, request: Request,
    dry_run: bool = Query(False),
    mapping_id: int | None = Form(None),
    mapping: str | None = Form(None),
):
    data = await _read(file)
    m = _resolve_mapping(db, "programs", mapping_id, mapping)
    return _run(db=db, data=data, filename=file.filename, kind="programs", user=current,
                request=request, dry_run=dry_run, mapping=m)


@router.post("/grades", summary="导入成绩")
async def import_grades(
    db: DbSession, file: UploadFile, current: CurrentUser, request: Request,
    dry_run: bool = Query(False),
    mapping_id: int | None = Form(None),
    mapping: str | None = Form(None),
):
    data = await _read(file)
    m = _resolve_mapping(db, "grades", mapping_id, mapping)
    return _run(db=db, data=data, filename=file.filename, kind="grades", user=current,
                request=request, dry_run=dry_run, mapping=m)


@router.get("/templates", summary="导入模板列名说明")
def templates():
    return {
        "students": importer.STUDENT_COLUMNS,
        "courses": importer.COURSE_COLUMNS,
        "programs": importer.PROGRAM_COLUMNS,
        "grades": importer.GRADE_COLUMNS,
    }


# ----- 历史批次 -----

@router.get("/batches", response_model=ImportBatchPage, summary="导入历史列表")
def list_batches(
    db: DbSession,
    kind: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    stmt = select(ImportBatch)
    count_stmt = select(func.count(ImportBatch.id))
    if kind:
        stmt = stmt.where(ImportBatch.kind == kind)
        count_stmt = count_stmt.where(ImportBatch.kind == kind)
    stmt = stmt.order_by(ImportBatch.id.desc()).offset((page - 1) * size).limit(size)
    items = list(db.scalars(stmt))
    total = db.scalar(count_stmt) or 0
    return ImportBatchPage(
        items=[ImportBatchSummary.model_validate(i) for i in items],
        total=total,
    )


@router.get("/batches/{batch_id}", response_model=ImportBatchDetail, summary="导入批次详情（含错误明细）")
def get_batch(batch_id: int, db: DbSession):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    return ImportBatchDetail.model_validate(batch)


# ----- 字段映射模板 CRUD -----

@router.get("/mappings", response_model=list[ImportMappingRead], summary="字段映射模板列表")
def list_mappings(db: DbSession, kind: str | None = None):
    stmt = select(ImportMapping).order_by(ImportMapping.kind, ImportMapping.name)
    if kind:
        stmt = stmt.where(ImportMapping.kind == kind)
    return [ImportMappingRead.model_validate(m) for m in db.scalars(stmt)]


@router.post("/mappings", response_model=ImportMappingRead, summary="新建映射模板")
def create_mapping(payload: ImportMappingCreate, db: DbSession, current: CurrentUser):
    if db.scalar(select(ImportMapping).where(
        ImportMapping.kind == payload.kind, ImportMapping.name == payload.name,
    )):
        raise HTTPException(status.HTTP_409_CONFLICT, "同类型下已存在同名模板")
    m = ImportMapping(
        kind=payload.kind, name=payload.name, mapping=payload.mapping,
        is_default=payload.is_default, created_by=current.id,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return ImportMappingRead.model_validate(m)


@router.put("/mappings/{mapping_id}", response_model=ImportMappingRead, summary="更新映射模板")
def update_mapping(mapping_id: int, payload: ImportMappingUpdate, db: DbSession):
    m = db.get(ImportMapping, mapping_id)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return ImportMappingRead.model_validate(m)


@router.delete("/mappings/{mapping_id}", summary="删除映射模板")
def delete_mapping(mapping_id: int, db: DbSession):
    m = db.get(ImportMapping, mapping_id)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.get("/batches/{batch_id}/errors.xlsx", summary="下载导入错误清单 Excel")
def download_batch_errors(batch_id: int, db: DbSession):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "批次不存在")
    wb = Workbook()
    ws = wb.active
    ws.title = "errors"
    ws.append(["行号", "错误信息"])
    for e in batch.errors or []:
        ws.append([e.get("row"), e.get("message")])
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 80
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    safe_name = f"import_errors_batch{batch_id}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )

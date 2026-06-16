from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_staff
from app.core.logging import get_logger
from app.models.import_batch import ImportBatch
from app.schemas.import_batch import ImportBatchDetail, ImportBatchPage, ImportBatchSummary
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


def _run(*, db, data: bytes, filename: str, kind: str, user, request):
    """所有 import_* 端点的统一路径：解析 → run_import → 审计 → 返回汇总。"""
    try:
        df = importer.parse_table(data, filename)
    except ValueError as e:
        log.warning("import_parse_error", kind=kind, filename=filename, error=str(e))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    try:
        batch = importer.run_import(
            db, kind=kind, df=df, operator_id=user.id if user else None,
            filename=filename,
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
            "created": batch.created_count,
            "updated": batch.updated_count,
            "skipped": batch.skipped_count,
            "error_count": batch.error_count,
        },
        request=request,
    )
    db.commit()
    db.refresh(batch)
    return {
        "batch_id": batch.id,
        "status": batch.status,
        "created": batch.created_count,
        "updated": batch.updated_count,
        "skipped": batch.skipped_count,
        "errors": batch.errors or [],
    }


@router.post("/students", summary="导入学生名册")
async def import_students(db: DbSession, file: UploadFile, current: CurrentUser, request: Request):
    data = await _read(file)
    return _run(db=db, data=data, filename=file.filename, kind="students", user=current, request=request)


@router.post("/courses", summary="导入课程主数据")
async def import_courses(db: DbSession, file: UploadFile, current: CurrentUser, request: Request):
    data = await _read(file)
    return _run(db=db, data=data, filename=file.filename, kind="courses", user=current, request=request)


@router.post("/programs", summary="导入培养方案 + 学分桶 + 课程映射")
async def import_program(db: DbSession, file: UploadFile, current: CurrentUser, request: Request):
    data = await _read(file)
    return _run(db=db, data=data, filename=file.filename, kind="programs", user=current, request=request)


@router.post("/grades", summary="导入成绩")
async def import_grades(db: DbSession, file: UploadFile, current: CurrentUser, request: Request):
    data = await _read(file)
    return _run(db=db, data=data, filename=file.filename, kind="grades", user=current, request=request)


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

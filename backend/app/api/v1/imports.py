from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status

from app.api.deps import CurrentUser, DbSession, require_staff
from app.core.logging import get_logger
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


def _run(db, df_loader, importer_fn, *, kind: str, filename: str, user, request):
    log.info("import_start", kind=kind, filename=filename)
    try:
        df = df_loader()
        result = importer_fn(db, df)
        status_str = "completed"
        if result.errors and result.created == 0 and result.updated == 0:
            db.rollback()
            status_str = "rolled_back"
            log.warning(
                "import_rollback_all_failed",
                kind=kind, filename=filename, error_count=len(result.errors),
            )
        # 重新开启事务以写审计
        record_audit(
            db, user=user, action=f"imports.{kind}",
            resource_type="import", resource_id=filename,
            detail={
                "filename": filename,
                "status": status_str,
                "created": result.created,
                "updated": result.updated,
                "skipped": result.skipped,
                "error_count": len(result.errors),
            },
            request=request,
        )
        db.commit()
        if status_str == "completed":
            log.info(
                "import_finish",
                kind=kind, filename=filename,
                created=result.created, updated=result.updated,
                skipped=result.skipped, error_count=len(result.errors),
            )
        return result.__dict__
    except ValueError as e:
        db.rollback()
        log.warning("import_parse_error", kind=kind, filename=filename, error=str(e))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except Exception:
        db.rollback()
        log.exception("import_exception", kind=kind, filename=filename)
        raise


@router.post("/students", summary="导入学生名册")
async def import_students(db: DbSession, file: UploadFile, current: CurrentUser, request: Request):
    data = await _read(file)
    return _run(db, lambda: importer.parse_table(data, file.filename), importer.import_students,
                kind="students", filename=file.filename, user=current, request=request)


@router.post("/courses", summary="导入课程主数据")
async def import_courses(db: DbSession, file: UploadFile, current: CurrentUser, request: Request):
    data = await _read(file)
    return _run(db, lambda: importer.parse_table(data, file.filename), importer.import_courses,
                kind="courses", filename=file.filename, user=current, request=request)


@router.post("/programs", summary="导入培养方案 + 学分桶 + 课程映射")
async def import_program(db: DbSession, file: UploadFile, current: CurrentUser, request: Request):
    data = await _read(file)
    return _run(db, lambda: importer.parse_table(data, file.filename), importer.import_program,
                kind="programs", filename=file.filename, user=current, request=request)


@router.post("/grades", summary="导入成绩")
async def import_grades(db: DbSession, file: UploadFile, current: CurrentUser, request: Request):
    data = await _read(file)
    return _run(db, lambda: importer.parse_table(data, file.filename), importer.import_grades,
                kind="grades", filename=file.filename, user=current, request=request)


@router.get("/templates", summary="导入模板列名说明")
def templates():
    return {
        "students": importer.STUDENT_COLUMNS,
        "courses": importer.COURSE_COLUMNS,
        "programs": importer.PROGRAM_COLUMNS,
        "grades": importer.GRADE_COLUMNS,
    }

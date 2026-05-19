from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.deps import DbSession, require_staff
from app.services import importer

router = APIRouter(dependencies=[Depends(require_staff)])


async def _read(file: UploadFile) -> bytes:
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "缺少文件名")
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件为空")
    return data


def _run(db, df_loader, importer_fn):
    try:
        df = df_loader()
        result = importer_fn(db, df)
        if result.errors and result.created == 0 and result.updated == 0:
            db.rollback()
        else:
            db.commit()
        return result.__dict__
    except ValueError as e:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except Exception:
        db.rollback()
        raise


@router.post("/students", summary="导入学生名册")
async def import_students(db: DbSession, file: UploadFile):
    data = await _read(file)
    return _run(db, lambda: importer.parse_table(data, file.filename), importer.import_students)


@router.post("/courses", summary="导入课程主数据")
async def import_courses(db: DbSession, file: UploadFile):
    data = await _read(file)
    return _run(db, lambda: importer.parse_table(data, file.filename), importer.import_courses)


@router.post("/programs", summary="导入培养方案 + 学分桶 + 课程映射")
async def import_program(db: DbSession, file: UploadFile):
    data = await _read(file)
    return _run(db, lambda: importer.parse_table(data, file.filename), importer.import_program)


@router.post("/grades", summary="导入成绩")
async def import_grades(db: DbSession, file: UploadFile):
    data = await _read(file)
    return _run(db, lambda: importer.parse_table(data, file.filename), importer.import_grades)


@router.get("/templates", summary="导入模板列名说明")
def templates():
    return {
        "students": importer.STUDENT_COLUMNS,
        "courses": importer.COURSE_COLUMNS,
        "programs": importer.PROGRAM_COLUMNS,
        "grades": importer.GRADE_COLUMNS,
    }

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_staff
from app.api.v1._helpers import get_or_404
from app.models.student import Student
from app.models.user import UserRole
from app.models.warning import Warning
from app.schemas.warning import WarningRead
from app.services.warning_engine import generate_batch, generate_for_student

router = APIRouter()


class GenerateRequest(BaseModel):
    student_ids: list[int] | None = None  # 空 = 全部
    semester: str | None = None
    college: str | None = None
    major: str | None = None
    enroll_year: int | None = None


class ResolveRequest(BaseModel):
    note: str | None = None


@router.get("", response_model=list[WarningRead])
def list_warnings(
    db: DbSession,
    current: CurrentUser,
    student_id: int | None = None,
    level: str | None = None,
    semester: str | None = None,
    only_open: bool = False,
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Warning)
    if current.role == UserRole.STUDENT:
        me = db.scalar(select(Student).where(Student.user_id == current.id))
        if not me:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "未关联学生信息")
        stmt = stmt.where(Warning.student_id == me.id)
    elif student_id is not None:
        stmt = stmt.where(Warning.student_id == student_id)

    if level:
        stmt = stmt.where(Warning.level == level)
    if semester:
        stmt = stmt.where(Warning.semester == semester)
    if only_open:
        stmt = stmt.where(Warning.resolved_at.is_(None))

    return db.scalars(stmt.order_by(Warning.created_at.desc()).offset(skip).limit(limit)).all()


@router.get("/{warning_id}", response_model=WarningRead)
def get_warning(warning_id: int, db: DbSession, current: CurrentUser):
    w = get_or_404(db, Warning, warning_id, "预警")
    if current.role == UserRole.STUDENT:
        me = db.scalar(select(Student).where(Student.user_id == current.id))
        if not me or me.id != w.student_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该预警")
    return w


@router.post("/generate", dependencies=[Depends(require_staff)], summary="批量生成预警")
def generate(payload: GenerateRequest, db: DbSession):
    stmt = select(Student)
    if payload.student_ids:
        stmt = stmt.where(Student.id.in_(payload.student_ids))
    if payload.college:
        stmt = stmt.where(Student.college == payload.college)
    if payload.major:
        stmt = stmt.where(Student.major == payload.major)
    if payload.enroll_year is not None:
        stmt = stmt.where(Student.enroll_year == payload.enroll_year)
    students = list(db.scalars(stmt))
    if not students:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未匹配到学生")
    return generate_batch(db, students, semester=payload.semester)


@router.post("/students/{student_id}/generate", dependencies=[Depends(require_staff)], summary="单学生触发预警")
def generate_one(student_id: int, db: DbSession, semester: str | None = None):
    student = get_or_404(db, Student, student_id, "学生")
    w = generate_for_student(db, student, semester=semester)
    if not w:
        db.commit()
        return {"generated": False, "reason": "完成度达标，无需预警"}
    db.commit()
    db.refresh(w)
    return {"generated": True, "warning_id": w.id, "level": w.level, "summary": w.summary}


@router.post("/{warning_id}/resolve", response_model=WarningRead, dependencies=[Depends(require_staff)])
def resolve(warning_id: int, payload: ResolveRequest, db: DbSession):
    w = get_or_404(db, Warning, warning_id, "预警")
    w.resolved_at = datetime.now(timezone.utc)
    if payload.note:
        w.resolver_note = payload.note
    db.commit()
    db.refresh(w)
    return w

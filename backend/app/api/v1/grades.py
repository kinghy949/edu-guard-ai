from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_staff
from app.api.v1._helpers import apply_updates, get_or_404
from app.models.grade import Grade
from app.models.student import Student
from app.models.user import UserRole
from app.schemas.grade import GradeCreate, GradeRead, GradeUpdate

router = APIRouter()


@router.get("", response_model=list[GradeRead])
def list_grades(
    db: DbSession,
    current: CurrentUser,
    student_id: int | None = None,
    semester: str | None = None,
    skip: int = 0,
    limit: int = 200,
):
    stmt = select(Grade)

    if current.role == UserRole.STUDENT:
        me = db.scalar(select(Student).where(Student.user_id == current.id))
        if not me:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "未关联学生信息")
        stmt = stmt.where(Grade.student_id == me.id)
    elif student_id is not None:
        stmt = stmt.where(Grade.student_id == student_id)

    if semester:
        stmt = stmt.where(Grade.semester == semester)
    return db.scalars(stmt.offset(skip).limit(limit)).all()


@router.post("", response_model=GradeRead, dependencies=[Depends(require_staff)])
def create_grade(payload: GradeCreate, db: DbSession):
    grade = Grade(**payload.model_dump())
    db.add(grade)
    db.commit()
    db.refresh(grade)
    return grade


@router.patch("/{grade_id}", response_model=GradeRead, dependencies=[Depends(require_staff)])
def update_grade(grade_id: int, payload: GradeUpdate, db: DbSession):
    grade = get_or_404(db, Grade, grade_id, "成绩")
    apply_updates(grade, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(grade)
    return grade


@router.delete("/{grade_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_staff)])
def delete_grade(grade_id: int, db: DbSession):
    grade = get_or_404(db, Grade, grade_id, "成绩")
    db.delete(grade)
    db.commit()

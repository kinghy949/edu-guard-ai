from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_staff
from app.api.v1._helpers import apply_updates, get_or_404
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate

router = APIRouter()


def _ensure_can_read(current: User, student: Student) -> None:
    if current.role in {UserRole.ADMIN, UserRole.COUNSELOR}:
        return
    if current.role == UserRole.STUDENT and student.user_id == current.id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该学生")


@router.get("", response_model=list[StudentRead], dependencies=[Depends(require_staff)])
def list_students(
    db: DbSession,
    skip: int = 0,
    limit: int = 100,
    college: str | None = None,
    major: str | None = None,
    enroll_year: int | None = None,
):
    stmt = select(Student)
    if college:
        stmt = stmt.where(Student.college == college)
    if major:
        stmt = stmt.where(Student.major == major)
    if enroll_year:
        stmt = stmt.where(Student.enroll_year == enroll_year)
    return db.scalars(stmt.offset(skip).limit(limit)).all()


@router.post("", response_model=StudentRead, dependencies=[Depends(require_staff)])
def create_student(payload: StudentCreate, db: DbSession):
    if not db.get(User, payload.user_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "关联用户不存在")
    exists = db.scalar(select(Student).where(Student.student_no == payload.student_no))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "学号已存在")
    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/me", response_model=StudentRead)
def my_profile(db: DbSession, current: CurrentUser):
    student = db.scalar(select(Student).where(Student.user_id == current.id))
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未关联学生信息")
    return student


@router.get("/{student_id}", response_model=StudentRead)
def get_student(student_id: int, db: DbSession, current: CurrentUser):
    student = get_or_404(db, Student, student_id, "学生")
    _ensure_can_read(current, student)
    return student


@router.patch("/{student_id}", response_model=StudentRead, dependencies=[Depends(require_staff)])
def update_student(student_id: int, payload: StudentUpdate, db: DbSession):
    student = get_or_404(db, Student, student_id, "学生")
    apply_updates(student, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_staff)])
def delete_student(student_id: int, db: DbSession):
    student = get_or_404(db, Student, student_id, "学生")
    db.delete(student)
    db.commit()

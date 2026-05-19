from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, require_staff
from app.api.v1._helpers import apply_updates, get_or_404
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate

router = APIRouter()


@router.get("", response_model=list[CourseRead])
def list_courses(db: DbSession, skip: int = 0, limit: int = 100, q: str | None = None):
    stmt = select(Course)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Course.name.like(like)) | (Course.code.like(like)))
    return db.scalars(stmt.offset(skip).limit(limit)).all()


@router.get("/{course_id}", response_model=CourseRead)
def get_course(course_id: int, db: DbSession):
    return get_or_404(db, Course, course_id, "课程")


@router.post("", response_model=CourseRead, dependencies=[Depends(require_staff)])
def create_course(payload: CourseCreate, db: DbSession):
    if db.scalar(select(Course).where(Course.code == payload.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "课程编码已存在")
    course = Course(**payload.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.patch("/{course_id}", response_model=CourseRead, dependencies=[Depends(require_staff)])
def update_course(course_id: int, payload: CourseUpdate, db: DbSession):
    course = get_or_404(db, Course, course_id, "课程")
    apply_updates(course, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_staff)])
def delete_course(course_id: int, db: DbSession):
    course = get_or_404(db, Course, course_id, "课程")
    db.delete(course)
    db.commit()

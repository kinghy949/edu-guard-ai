from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_staff
from app.api.v1._helpers import get_or_404
from app.models.student import Student
from app.models.user import UserRole
from app.services.credit_compare import compute_student_progress, report_to_dict

router = APIRouter()


@router.get("/me", summary="当前学生学业完成度")
def my_progress(db: DbSession, current: CurrentUser):
    student = db.scalar(select(Student).where(Student.user_id == current.id))
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "未关联学生信息")
    return report_to_dict(compute_student_progress(db, student))


@router.get("/{student_id}", summary="指定学生完成度", dependencies=[Depends(require_staff)])
def student_progress(student_id: int, db: DbSession):
    student = get_or_404(db, Student, student_id, "学生")
    return report_to_dict(compute_student_progress(db, student))

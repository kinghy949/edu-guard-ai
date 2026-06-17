from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select

from app.api.deps import CurrentUser, DbSession, require_staff
from app.api.v1._helpers import apply_updates, get_or_404
from app.models.course import Course
from app.models.grade import Grade
from app.models.snapshot import StudentProgressSnapshot
from app.models.student import Student
from app.models.user import User, UserRole
from app.models.warning import Warning, WarningStatus
from app.schemas.student import (
    StudentCreate,
    StudentListItem,
    StudentListPage,
    StudentRead,
    StudentUpdate,
)

router = APIRouter()

_LEVEL_RANK = {"info": 1, "warn": 2, "severe": 3}


def _ensure_can_read(current: User, student: Student) -> None:
    if current.role in {UserRole.ADMIN, UserRole.COUNSELOR}:
        return
    if current.role == UserRole.STUDENT and student.user_id == current.id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该学生")


@router.get("", response_model=StudentListPage, dependencies=[Depends(require_staff)])
def list_students(
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    keyword: str | None = Query(None, description="学号 / 姓名 模糊"),
    college: str | None = None,
    major: str | None = None,
    class_name: str | None = None,
    enroll_year: int | None = None,
    has_open_warning: bool | None = None,
    warning_level: str | None = None,
    completion_lt: float | None = None,
    sort: str = Query("student_no", pattern="^(student_no|completion_asc|completion_desc)$"),
):
    # 子查询：每个学生最高未处理预警级别（数字 rank）
    open_status = (WarningStatus.OPEN, WarningStatus.FOLLOWING)
    rank_case = case(
        (Warning.level == "severe", 3),
        (Warning.level == "warn", 2),
        (Warning.level == "info", 1),
        else_=0,
    )
    open_w = (
        select(
            Warning.student_id.label("sid"),
            func.max(rank_case).label("max_rank"),
        )
        .where(Warning.status.in_(open_status))
        .group_by(Warning.student_id)
        .subquery()
    )

    stmt = (
        select(Student, StudentProgressSnapshot.completion_ratio, open_w.c.max_rank)
        .outerjoin(StudentProgressSnapshot, StudentProgressSnapshot.student_id == Student.id)
        .outerjoin(open_w, open_w.c.sid == Student.id)
    )
    count_stmt = select(func.count(Student.id))

    def _apply_filters(s):
        if college:
            s = s.where(Student.college == college)
        if major:
            s = s.where(Student.major == major)
        if class_name:
            s = s.where(Student.class_name == class_name)
        if enroll_year is not None:
            s = s.where(Student.enroll_year == enroll_year)
        if keyword:
            kw = f"%{keyword}%"
            s = s.where(or_(Student.student_no.ilike(kw), Student.name.ilike(kw)))
        return s

    stmt = _apply_filters(stmt)
    count_stmt = _apply_filters(count_stmt)

    if has_open_warning is True:
        stmt = stmt.where(open_w.c.max_rank.is_not(None))
        count_stmt = count_stmt.where(
            Student.id.in_(select(open_w.c.sid))
        )
    elif has_open_warning is False:
        stmt = stmt.where(open_w.c.max_rank.is_(None))
        count_stmt = count_stmt.where(
            ~Student.id.in_(select(open_w.c.sid))
        )

    if warning_level:
        target_rank = _LEVEL_RANK.get(warning_level, 0)
        stmt = stmt.where(open_w.c.max_rank >= target_rank)
        count_stmt = count_stmt.where(
            Student.id.in_(
                select(Warning.student_id)
                .where(Warning.status.in_(open_status), Warning.level == warning_level)
            )
        )

    if completion_lt is not None:
        stmt = stmt.where(StudentProgressSnapshot.completion_ratio < completion_lt)
        count_stmt = count_stmt.where(
            Student.id.in_(
                select(StudentProgressSnapshot.student_id)
                .where(StudentProgressSnapshot.completion_ratio < completion_lt)
            )
        )

    if sort == "completion_asc":
        stmt = stmt.order_by(StudentProgressSnapshot.completion_ratio.asc().nullslast())
    elif sort == "completion_desc":
        stmt = stmt.order_by(StudentProgressSnapshot.completion_ratio.desc().nullslast())
    else:
        stmt = stmt.order_by(Student.student_no.asc())

    stmt = stmt.offset((page - 1) * size).limit(size)
    rows = db.execute(stmt).all()
    total = db.scalar(count_stmt) or 0

    items: list[StudentListItem] = []
    rank_to_level = {3: "severe", 2: "warn", 1: "info"}
    for student, completion, max_rank in rows:
        item_data = StudentListItem.model_validate(student, from_attributes=True).model_dump()
        item_data["completion_ratio"] = float(completion) if completion is not None else None
        item_data["open_warning_level"] = rank_to_level.get(int(max_rank)) if max_rank else None
        items.append(StudentListItem.model_validate(item_data))

    return StudentListPage(items=items, total=int(total))


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


@router.get("/{student_id}/transcript", summary="按学期分组的成绩单")
def get_transcript(student_id: int, db: DbSession, current: CurrentUser):
    student = get_or_404(db, Student, student_id, "学生")
    _ensure_can_read(current, student)
    rows = list(db.execute(
        select(Grade, Course)
        .join(Course, Course.id == Grade.course_id)
        .where(Grade.student_id == student.id)
        .order_by(Grade.semester, Course.code)
    ))
    by_semester: dict[str, list[dict]] = {}
    for grade, course in rows:
        by_semester.setdefault(grade.semester, []).append({
            "code": course.code,
            "name": course.name,
            "credits": str(course.credits),
            "credits_earned": str(grade.credits_earned),
            "score": str(grade.score) if grade.score is not None else None,
            "status": grade.status,
            "semester": grade.semester,
        })
    semesters = sorted(by_semester.keys())
    return [{"semester": s, "courses": by_semester[s]} for s in semesters]

"""培养方案-成绩 比对引擎。

给定学生，按培养方案的学分桶累计已修 / 在修学分，输出缺口与推荐补修课。

约定：
- ``status=completed`` → 计入 earned
- ``status=in_progress`` 或 ``retake`` → 计入 in_progress（缺口预估时也扣减）
- ``status=failed`` → 不计入
- 一门课在方案中只归属一个桶（由 ``program_courses.bucket_id`` 决定）；
  若学生修了"方案外课程"，归入虚拟桶 ``__other__``，不抵消方案缺口。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.grade import Grade, GradeStatus
from app.models.program import CreditBucket, Program, ProgramCourse
from app.models.student import Student

ZERO = Decimal("0")


@dataclass
class CourseLite:
    id: int
    code: str
    name: str
    credits: Decimal
    is_required: bool = False
    semester_suggested: int | None = None


@dataclass
class BucketProgress:
    bucket_id: int | None  # None 表示虚拟桶（方案外）
    category: str
    required: Decimal
    earned: Decimal = ZERO
    in_progress: Decimal = ZERO
    recommended: list[CourseLite] = field(default_factory=list)

    @property
    def gap(self) -> Decimal:
        return max(self.required - self.earned - self.in_progress, ZERO)

    @property
    def completion_ratio(self) -> float:
        if self.required <= 0:
            return 1.0
        return float(min(self.earned / self.required, Decimal("1")))


@dataclass
class ProgressReport:
    student_id: int
    student_no: str
    student_name: str
    program_id: int | None
    program_name: str | None
    total_required: Decimal
    total_earned: Decimal
    total_in_progress: Decimal
    buckets: list[BucketProgress]
    failed_courses: list[CourseLite] = field(default_factory=list)

    @property
    def total_gap(self) -> Decimal:
        return max(self.total_required - self.total_earned - self.total_in_progress, ZERO)


def compute_student_progress(db: Session, student: Student) -> ProgressReport:
    program: Program | None = db.get(Program, student.program_id) if student.program_id else None

    # 拉取方案下的 buckets 与 program_course 映射
    buckets: list[CreditBucket] = []
    pc_by_course: dict[int, ProgramCourse] = {}
    courses_in_program: dict[int, Course] = {}
    if program:
        buckets = list(db.scalars(select(CreditBucket).where(CreditBucket.program_id == program.id)))
        {b.id: b for b in buckets}
        program_courses = list(db.scalars(select(ProgramCourse).where(ProgramCourse.program_id == program.id)))
        pc_by_course = {pc.course_id: pc for pc in program_courses}
        if program_courses:
            courses_in_program = {
                c.id: c for c in db.scalars(
                    select(Course).where(Course.id.in_([pc.course_id for pc in program_courses]))
                )
            }

    progress_map: dict[int | None, BucketProgress] = {
        b.id: BucketProgress(bucket_id=b.id, category=b.category, required=Decimal(b.credits_required))
        for b in buckets
    }
    # 虚拟桶：方案外课程
    other_bucket = BucketProgress(bucket_id=None, category="__other__", required=ZERO)

    # 拉取学生成绩 + 课程
    grades = list(db.scalars(select(Grade).where(Grade.student_id == student.id)))
    course_ids = {g.course_id for g in grades}
    grade_courses: dict[int, Course] = {}
    if course_ids:
        grade_courses = {c.id: c for c in db.scalars(select(Course).where(Course.id.in_(course_ids)))}

    taken_course_ids: set[int] = set()
    failed: list[CourseLite] = []

    for g in grades:
        course = grade_courses.get(g.course_id)
        if not course:
            continue
        pc = pc_by_course.get(g.course_id)
        target = progress_map[pc.bucket_id] if pc else other_bucket
        credits = Decimal(g.credits_earned or 0)

        if g.status == GradeStatus.COMPLETED:
            target.earned += credits
            taken_course_ids.add(g.course_id)
        elif g.status in (GradeStatus.IN_PROGRESS, GradeStatus.RETAKE):
            target.in_progress += Decimal(course.credits)
            taken_course_ids.add(g.course_id)
        elif g.status == GradeStatus.FAILED:
            failed.append(CourseLite(
                id=course.id, code=course.code, name=course.name, credits=Decimal(course.credits),
            ))

    # 推荐补修：本桶 program_courses 中未修/未在修的课，优先必修，再按建议学期排序
    for bp in progress_map.values():
        if bp.gap <= 0:
            continue
        candidates = [
            pc for pc in pc_by_course.values()
            if pc.bucket_id == bp.bucket_id and pc.course_id not in taken_course_ids
        ]
        candidates.sort(key=lambda pc: (not pc.is_required, pc.semester_suggested or 99))
        for pc in candidates[:10]:
            c = courses_in_program.get(pc.course_id)
            if not c:
                continue
            bp.recommended.append(CourseLite(
                id=c.id, code=c.code, name=c.name, credits=Decimal(c.credits),
                is_required=pc.is_required, semester_suggested=pc.semester_suggested,
            ))

    buckets_out = list(progress_map.values())
    if other_bucket.earned > 0 or other_bucket.in_progress > 0:
        buckets_out.append(other_bucket)

    total_required = Decimal(program.total_credits_required) if program else sum(
        (b.required for b in progress_map.values()), ZERO
    )
    total_earned = sum((b.earned for b in buckets_out), ZERO)
    total_in_progress = sum((b.in_progress for b in buckets_out), ZERO)

    return ProgressReport(
        student_id=student.id,
        student_no=student.student_no,
        student_name=student.name,
        program_id=program.id if program else None,
        program_name=program.name if program else None,
        total_required=total_required,
        total_earned=total_earned,
        total_in_progress=total_in_progress,
        buckets=buckets_out,
        failed_courses=failed,
    )


def report_to_dict(r: ProgressReport) -> dict:
    return {
        "student_id": r.student_id,
        "student_no": r.student_no,
        "student_name": r.student_name,
        "program_id": r.program_id,
        "program_name": r.program_name,
        "total_required": str(r.total_required),
        "total_earned": str(r.total_earned),
        "total_in_progress": str(r.total_in_progress),
        "total_gap": str(r.total_gap),
        "buckets": [
            {
                "bucket_id": b.bucket_id,
                "category": b.category,
                "required": str(b.required),
                "earned": str(b.earned),
                "in_progress": str(b.in_progress),
                "gap": str(b.gap),
                "completion_ratio": round(b.completion_ratio, 4),
                "recommended": [
                    {
                        "id": c.id, "code": c.code, "name": c.name,
                        "credits": str(c.credits),
                        "is_required": c.is_required,
                        "semester_suggested": c.semester_suggested,
                    } for c in b.recommended
                ],
            } for b in r.buckets
        ],
        "failed_courses": [
            {"id": c.id, "code": c.code, "name": c.name, "credits": str(c.credits)}
            for c in r.failed_courses
        ],
    }


def iter_progress(db: Session, students: Iterable[Student]) -> Iterable[ProgressReport]:
    for s in students:
        yield compute_student_progress(db, s)


def build_academic_map(db: Session, student: Student) -> dict:
    """学业地图：按学分桶分组返回方案课程及其状态。

    每门课状态取值：
      - completed: 该课最新成绩通过
      - in_progress: 在修/重修中
      - failed: 最新一次为 failed 且无后续 completed/in_progress
      - retake: 在 retake 状态（视为 in_progress 的子类）
      - not_taken: 学生从未修过
    """
    if not student.program_id:
        return {"program_id": None, "buckets": [], "recommended": []}

    program = db.get(Program, student.program_id)
    buckets = list(db.scalars(select(CreditBucket).where(CreditBucket.program_id == student.program_id)))
    pcs = list(db.scalars(select(ProgramCourse).where(ProgramCourse.program_id == student.program_id)))
    if not pcs:
        return {"program_id": program.id if program else None, "program_name": program.name if program else None,
                "buckets": [], "recommended": []}
    courses = {c.id: c for c in db.scalars(
        select(Course).where(Course.id.in_([pc.course_id for pc in pcs]))
    )}
    grades = list(db.scalars(select(Grade).where(Grade.student_id == student.id)))
    grades_by_course: dict[int, list[Grade]] = {}
    for g in grades:
        grades_by_course.setdefault(g.course_id, []).append(g)

    def _status_for(course_id: int) -> tuple[str, Decimal | None, str | None]:
        gs = sorted(grades_by_course.get(course_id, []),
                    key=lambda g: g.semester, reverse=True)
        if not gs:
            return "not_taken", None, None
        # 任一历史已通过 → completed
        if any(g.status == GradeStatus.COMPLETED for g in gs):
            for g in gs:
                if g.status == GradeStatus.COMPLETED:
                    return "completed", g.score, g.semester
        latest = gs[0]
        if latest.status == GradeStatus.IN_PROGRESS:
            return "in_progress", latest.score, latest.semester
        if latest.status == GradeStatus.RETAKE:
            return "retake", latest.score, latest.semester
        if latest.status == GradeStatus.FAILED:
            return "failed", latest.score, latest.semester
        return "not_taken", None, None

    buckets_out = []
    pcs_by_bucket: dict[int, list[ProgramCourse]] = {}
    for pc in pcs:
        pcs_by_bucket.setdefault(pc.bucket_id or 0, []).append(pc)

    for b in buckets:
        bucket_courses = []
        for pc in pcs_by_bucket.get(b.id, []):
            c = courses.get(pc.course_id)
            if not c:
                continue
            status, score, semester = _status_for(c.id)
            bucket_courses.append({
                "id": c.id, "code": c.code, "name": c.name,
                "credits": str(c.credits),
                "is_required": pc.is_required,
                "semester_suggested": pc.semester_suggested,
                "status": status,
                "score": str(score) if score is not None else None,
                "semester": semester,
            })
        bucket_courses.sort(key=lambda x: (x["semester_suggested"] or 99, x["code"]))
        buckets_out.append({
            "bucket_id": b.id, "category": b.category,
            "required": str(b.credits_required),
            "courses": bucket_courses,
        })

    # 复用 compute_student_progress 提取的推荐补修课列表（含状态判断）
    report = compute_student_progress(db, student)
    recommended = []
    for bp in report.buckets:
        for c in bp.recommended:
            recommended.append({
                "bucket": bp.category,
                "id": c.id, "code": c.code, "name": c.name,
                "credits": str(c.credits),
                "is_required": c.is_required,
                "semester_suggested": c.semester_suggested,
            })
    recommended.sort(key=lambda x: (x["semester_suggested"] or 99, x["code"]))

    return {
        "program_id": program.id if program else None,
        "program_name": program.name if program else None,
        "buckets": buckets_out,
        "recommended": recommended,
    }

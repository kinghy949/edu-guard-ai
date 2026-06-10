from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.grade import GradeStatus
from app.services.credit_compare import compute_student_progress

from tests.conftest import make_course, make_grade, make_program_with_buckets, make_student


def test_student_without_program_has_empty_progress(db: Session) -> None:
    student = make_student(db, student_no="20240010")

    report = compute_student_progress(db, student)

    assert report.program_id is None
    assert report.total_required == Decimal("0")
    assert report.total_gap == Decimal("0")
    assert report.buckets == []


def test_empty_bucket_has_no_gap_when_requirement_is_zero(db: Session) -> None:
    program, _ = make_program_with_buckets(db, total_credits="0", buckets=[("必修", "0")])
    student = make_student(db, student_no="20240011", program=program)

    report = compute_student_progress(db, student)

    assert len(report.buckets) == 1
    assert report.buckets[0].gap == Decimal("0")
    assert report.buckets[0].completion_ratio == 1.0


def test_completed_in_progress_failed_and_retake_credits_are_counted_correctly(db: Session) -> None:
    program, buckets = make_program_with_buckets(db, total_credits="10", buckets=[("必修", "6"), ("选修", "4")])
    student = make_student(db, student_no="20240012", program=program)
    completed = make_course(db, code="CS101", name="程序设计", credits="2", program=program, bucket=buckets[0])
    in_progress = make_course(db, code="CS102", name="数据结构", credits="2", program=program, bucket=buckets[0])
    retake = make_course(db, code="CS103", name="数据库", credits="2", program=program, bucket=buckets[0])
    failed = make_course(db, code="CS104", name="操作系统", credits="2", program=program, bucket=buckets[1])
    other = make_course(db, code="PE101", name="体育", credits="1")

    make_grade(db, student=student, course=completed, status=GradeStatus.COMPLETED, credits_earned="2")
    make_grade(db, student=student, course=in_progress, status=GradeStatus.IN_PROGRESS)
    make_grade(db, student=student, course=retake, status=GradeStatus.RETAKE)
    make_grade(db, student=student, course=failed, status=GradeStatus.FAILED)
    make_grade(db, student=student, course=other, status=GradeStatus.COMPLETED, credits_earned="1")

    report = compute_student_progress(db, student)

    required = next(b for b in report.buckets if b.category == "必修")
    elective = next(b for b in report.buckets if b.category == "选修")
    outside = next(b for b in report.buckets if b.category == "__other__")
    assert required.earned == Decimal("2.00")
    assert required.in_progress == Decimal("4.00")
    assert required.gap == Decimal("0")
    assert elective.earned == Decimal("0")
    assert elective.in_progress == Decimal("0")
    assert elective.gap == Decimal("4.00")
    assert outside.earned == Decimal("1.00")
    assert len(report.failed_courses) == 1
    assert report.failed_courses[0].code == "CS104"


def test_gap_calculation_uses_earned_and_in_progress(db: Session) -> None:
    program, buckets = make_program_with_buckets(db, total_credits="6", buckets=[("必修", "6")])
    student = make_student(db, student_no="20240013", program=program)
    completed = make_course(db, code="CS201", name="离散数学", credits="2", program=program, bucket=buckets[0])
    in_progress = make_course(db, code="CS202", name="算法", credits="2", program=program, bucket=buckets[0])

    make_grade(db, student=student, course=completed, status=GradeStatus.COMPLETED, credits_earned="2")
    make_grade(db, student=student, course=in_progress, status=GradeStatus.IN_PROGRESS)

    report = compute_student_progress(db, student)

    bucket = report.buckets[0]
    assert bucket.gap == Decimal("2.00")
    assert report.total_gap == Decimal("2.00")


def test_recommendations_exclude_taken_courses_and_prioritize_required(db: Session) -> None:
    program, buckets = make_program_with_buckets(db, total_credits="8", buckets=[("必修", "8")])
    student = make_student(db, student_no="20240014", program=program)
    taken = make_course(
        db, code="CS301", name="计算机组成", credits="2", program=program, bucket=buckets[0], is_required=True
    )
    required = make_course(
        db,
        code="CS302",
        name="编译原理",
        credits="2",
        program=program,
        bucket=buckets[0],
        is_required=True,
        semester_suggested=3,
    )
    optional = make_course(
        db,
        code="CS303",
        name="专业选讲",
        credits="2",
        program=program,
        bucket=buckets[0],
        is_required=False,
        semester_suggested=1,
    )
    make_grade(db, student=student, course=taken, status=GradeStatus.COMPLETED, credits_earned="2")

    report = compute_student_progress(db, student)

    recommended_codes = [course.code for course in report.buckets[0].recommended]
    assert taken.code not in recommended_codes
    assert recommended_codes[:2] == [required.code, optional.code]

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.warning import Warning
from app.services.credit_compare import BucketProgress, CourseLite, ProgressReport
from app.services.warning_engine import (
    DEFAULT_RULE,
    WarningLevel,
    _evaluate,
    current_semester_label,
    estimated_stage,
    generate_batch,
    generate_for_student,
)
from tests.conftest import make_program_with_buckets, make_student


def _report(
    *,
    total_required: Decimal = Decimal("100"),
    buckets: list[BucketProgress] | None = None,
    failed: bool = False,
) -> ProgressReport:
    buckets = buckets or [
        BucketProgress(
            bucket_id=1,
            category="必修",
            required=Decimal("100"),
            earned=Decimal("100"),
            in_progress=Decimal("0"),
        )
    ]
    return ProgressReport(
        student_id=1,
        student_no="20240001",
        student_name="测试学生",
        program_id=1,
        program_name="测试方案",
        total_required=total_required,
        total_earned=sum((b.earned for b in buckets), Decimal("0")),
        total_in_progress=sum((b.in_progress for b in buckets), Decimal("0")),
        buckets=buckets,
        failed_courses=[
            CourseLite(id=1, code="CS101", name="程序设计", credits=Decimal("2"))
        ]
        if failed
        else [],
    )


def test_failed_course_triggers_severe_warning() -> None:
    outcome = _evaluate(_report(failed=True), stage=2, rule=DEFAULT_RULE)

    assert outcome is not None
    assert outcome[0] == WarningLevel.SEVERE.value
    assert "挂科" in outcome[1]


def test_low_required_completion_triggers_severe_warning() -> None:
    report = _report(
        buckets=[
            BucketProgress(bucket_id=1, category="必修", required=Decimal("10"), earned=Decimal("4")),
            BucketProgress(bucket_id=2, category="选修", required=Decimal("90"), earned=Decimal("90")),
        ]
    )

    outcome = _evaluate(report, stage=3, rule=DEFAULT_RULE)

    assert outcome is not None
    assert outcome[0] == WarningLevel.SEVERE.value
    assert "必修" in outcome[1]


def test_large_total_gap_after_mid_stage_triggers_severe_warning() -> None:
    report = _report(
        buckets=[
            BucketProgress(bucket_id=1, category="必修", required=Decimal("100"), earned=Decimal("40")),
        ]
    )

    outcome = _evaluate(report, stage=5, rule=DEFAULT_RULE)

    assert outcome is not None
    assert outcome[0] == WarningLevel.SEVERE.value
    assert "总学分" in outcome[1]


def test_warn_when_total_gap_exceeds_warning_threshold() -> None:
    report = _report(
        buckets=[
            BucketProgress(bucket_id=1, category="必修", required=Decimal("100"), earned=Decimal("74")),
        ]
    )

    outcome = _evaluate(report, stage=2, rule=DEFAULT_RULE)

    assert outcome is not None
    assert outcome[0] == WarningLevel.WARN.value


def test_warn_when_any_category_completion_is_low() -> None:
    report = _report(
        buckets=[
            BucketProgress(bucket_id=1, category="必修", required=Decimal("50"), earned=Decimal("50")),
            BucketProgress(bucket_id=2, category="选修", required=Decimal("50"), earned=Decimal("34")),
        ]
    )

    outcome = _evaluate(report, stage=2, rule=DEFAULT_RULE)

    assert outcome is not None
    assert outcome[0] == WarningLevel.WARN.value


def test_info_when_only_small_gap_exists() -> None:
    report = _report(
        buckets=[
            BucketProgress(bucket_id=1, category="必修", required=Decimal("100"), earned=Decimal("80")),
        ]
    )

    outcome = _evaluate(report, stage=2, rule=DEFAULT_RULE)

    assert outcome is not None
    assert outcome[0] == WarningLevel.INFO.value


def test_no_warning_when_requirements_are_met() -> None:
    assert _evaluate(_report(), stage=8, rule=DEFAULT_RULE) is None


def test_no_warning_when_total_requirement_is_zero() -> None:
    assert _evaluate(_report(total_required=Decimal("0"), buckets=[]), stage=1, rule=DEFAULT_RULE) is None


def test_estimated_stage_boundaries() -> None:
    assert estimated_stage(2024, datetime(2024, 3, 1)) == 1
    assert estimated_stage(2024, datetime(2024, 9, 1)) == 2
    assert estimated_stage(2018, datetime(2024, 9, 1)) == 8


def test_current_semester_label() -> None:
    assert current_semester_label(datetime(2024, 3, 1)) == "2023-1"
    assert current_semester_label(datetime(2024, 9, 1)) == "2024-2"


def test_generate_for_student_persists_warning(db: Session) -> None:
    program, _ = make_program_with_buckets(db, total_credits="10", buckets=[("必修", "10")])
    student = make_student(db, student_no="20240101", enroll_year=2024, program=program)

    warning = generate_for_student(db, student, semester="2024-2")

    assert warning is not None
    assert warning.id is not None
    assert warning.level == WarningLevel.SEVERE.value
    assert warning.semester == "2024-2"
    assert db.scalar(select(Warning).where(Warning.id == warning.id)) is warning


def test_generate_for_student_can_skip_persistence(db: Session) -> None:
    program, _ = make_program_with_buckets(db, code="SE2025", total_credits="10", buckets=[("必修", "10")])
    student = make_student(db, student_no="20250101", enroll_year=2024, program=program)

    warning = generate_for_student(db, student, semester="2024-2", persist=False)

    assert warning is not None
    assert warning.id is None
    assert db.scalar(select(Warning).where(Warning.student_id == student.id)) is None


def test_generate_batch_counts_created_warnings(db: Session) -> None:
    program, _ = make_program_with_buckets(db, code="SE2026", total_credits="10", buckets=[("必修", "10")])
    risky = make_student(db, student_no="20260101", enroll_year=2024, program=program)
    no_program = make_student(db, student_no="20260102", enroll_year=2024)

    result = generate_batch(db, [risky, no_program], semester="2024-2")

    assert result == {
        "semester": "2024-2",
        "created": 1,
        "by_level": {"info": 0, "warn": 0, "severe": 1},
    }

from __future__ import annotations

from decimal import Decimal

from app.models.grade import GradeStatus
from app.models.snapshot import StudentProgressSnapshot
from app.services.stats import (
    class_ranking,
    level_distribution,
    overview,
    refresh_snapshots,
    warning_trend,
)
from tests.conftest import (
    auth_header,
    make_course,
    make_grade,
    make_program_with_buckets,
    make_student,
    make_user,
    make_warning,
)


def _staff(db, *, username="stats_staff"):
    u = make_user(db, role="counselor", username=username, password="GoodPass1")
    db.commit()
    return u


def test_refresh_snapshots_writes_completion_ratio(client, db):
    _staff(db)
    program, buckets = make_program_with_buckets(
        db, total_credits="10", buckets=[("必修", "10")],
    )
    s = make_student(db, student_no="ST0001", program=program)
    c = make_course(db, code="C001", name="必修1", credits="6",
                    bucket=buckets[0], program=program, is_required=True)
    make_grade(db, student=s, course=c, credits_earned="6", score="80",
               status=GradeStatus.COMPLETED)
    db.commit()

    n = refresh_snapshots(db)
    assert n >= 1
    snap = db.get(StudentProgressSnapshot, s.id)
    assert snap is not None
    assert snap.total_required == Decimal("10.0")
    assert snap.total_earned == Decimal("6.0")
    assert abs(snap.completion_ratio - 0.6) < 0.001


def test_overview_counts_open_warnings_and_avg_completion(client, db):
    _staff(db)
    program, buckets = make_program_with_buckets(
        db, total_credits="10", buckets=[("必修", "10")],
    )
    s = make_student(db, student_no="ST0002", program=program)
    make_warning(db, student=s, level="severe")
    make_warning(db, student=s, level="info")
    db.commit()
    refresh_snapshots(db)

    out = overview(db)
    assert out["students_total"] >= 1
    assert out["warnings_open"]["severe"] >= 1
    assert out["warnings_open"]["info"] >= 1
    assert 0 <= out["avg_completion_ratio"] <= 1


def test_class_ranking_sorted_by_completion(client, db):
    _staff(db)
    program, _ = make_program_with_buckets(db)
    make_student(db, student_no="R0001", program=program, class_name="软工2401")
    make_student(db, student_no="R0002", program=program, class_name="软工2402")
    db.commit()
    refresh_snapshots(db)
    rows = class_ranking(db)
    if len(rows) >= 2:
        # 升序：第一行 avg_completion_ratio 应 ≤ 第二行
        assert rows[0]["avg_completion_ratio"] <= rows[1]["avg_completion_ratio"]


def test_distribution_dim_validation(client, db):
    _staff(db)
    program, _ = make_program_with_buckets(db)
    s = make_student(db, student_no="D0001", program=program, college="信息学院")
    make_warning(db, student=s, level="warn")
    db.commit()
    rows = level_distribution(db, dim="college")
    assert any(r["key"] == "信息学院" and r["warn"] >= 1 for r in rows)

    import pytest
    with pytest.raises(ValueError):
        level_distribution(db, dim="invalid")


def test_warning_trend_returns_recent_semesters(client, db):
    _staff(db)
    program, _ = make_program_with_buckets(db)
    s = make_student(db, student_no="T0001", program=program)
    make_warning(db, student=s, level="warn", semester="2024-1")
    make_warning(db, student=s, level="severe", semester="2024-2")
    db.commit()
    trend = warning_trend(db, semesters=10)
    sems = [r["semester"] for r in trend]
    assert "2024-1" in sems and "2024-2" in sems


def test_stats_api_permissions(client, db):
    staff = _staff(db, username="stats_perm")
    student = make_user(db, role="student", username="stats_stu", password="GoodPass1")
    db.commit()

    assert client.get("/api/v1/stats/overview", headers=auth_header(staff)).status_code == 200
    assert client.get("/api/v1/stats/overview", headers=auth_header(student)).status_code == 403
    assert client.get("/api/v1/stats/overview").status_code == 401


def test_refresh_snapshots_endpoint(client, db):
    staff = _staff(db, username="stats_refresh")
    program, _ = make_program_with_buckets(db)
    make_student(db, student_no="RS0001", program=program)
    db.commit()
    r = client.post("/api/v1/stats/refresh-snapshots", headers=auth_header(staff))
    assert r.status_code == 200
    assert r.json()["refreshed"] >= 1

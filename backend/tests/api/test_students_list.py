from __future__ import annotations

from app.services.stats import refresh_snapshots
from tests.conftest import (
    auth_header,
    make_program_with_buckets,
    make_student,
    make_user,
    make_warning,
)


def _staff(db):
    u = make_user(db, role="counselor", username="sl_staff")
    db.commit()
    return u


def test_pagination_total_and_items(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    for i in range(5):
        make_student(db, student_no=f"P{i:04d}", program=program)
    db.commit()
    r = client.get("/api/v1/students?page=1&size=2", headers=auth_header(staff))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 5
    assert len(body["items"]) == 2


def test_keyword_and_class_filter(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    make_student(db, student_no="K0001", program=program, class_name="软工2401", name="王明")
    make_student(db, student_no="K0002", program=program, class_name="软工2402", name="李华")
    db.commit()
    body = client.get("/api/v1/students?keyword=王", headers=auth_header(staff)).json()
    assert any(i["student_no"] == "K0001" for i in body["items"])
    assert all("王" in i["name"] or "K0001" in i["student_no"] for i in body["items"])

    body2 = client.get("/api/v1/students?class_name=软工2402", headers=auth_header(staff)).json()
    assert all(i["class_name"] == "软工2402" for i in body2["items"])


def test_has_open_warning_and_level_filter(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    s_warn = make_student(db, student_no="W0001", program=program)
    make_student(db, student_no="W0002", program=program)
    make_warning(db, student=s_warn, level="severe")
    db.commit()

    body = client.get("/api/v1/students?has_open_warning=true", headers=auth_header(staff)).json()
    nos = {i["student_no"] for i in body["items"]}
    assert "W0001" in nos
    assert "W0002" not in nos

    body2 = client.get("/api/v1/students?warning_level=severe", headers=auth_header(staff)).json()
    assert any(i["student_no"] == "W0001" and i["open_warning_level"] == "severe"
               for i in body2["items"])


def test_completion_lt_and_sort(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    make_student(db, student_no="C0001", program=program)
    make_student(db, student_no="C0002", program=program)
    db.commit()
    refresh_snapshots(db)

    body = client.get("/api/v1/students?completion_lt=0.5&sort=completion_asc",
                      headers=auth_header(staff)).json()
    for i in body["items"]:
        if i["completion_ratio"] is not None:
            assert i["completion_ratio"] < 0.5


def test_empty_snapshot_completion_is_null(client, db):
    staff = _staff(db)
    program, _ = make_program_with_buckets(db)
    make_student(db, student_no="N0001", program=program)
    db.commit()
    body = client.get("/api/v1/students", headers=auth_header(staff)).json()
    target = next((i for i in body["items"] if i["student_no"] == "N0001"), None)
    assert target is not None
    # 未刷新快照时 completion_ratio 为 null
    assert target["completion_ratio"] is None

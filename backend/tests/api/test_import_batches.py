from __future__ import annotations

import io

from sqlalchemy import select

from app.models.import_batch import ImportBatch, ImportBatchRow
from app.models.student import Student
from tests.conftest import make_user

STUDENT_CSV_HEADER = "student_no,name,enroll_year,college,major,class_name\n"


def _staff_headers(client, db, *, username="batch_staff"):
    make_user(db, role="counselor", username=username, password="GoodPass1")
    db.commit()
    r = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "GoodPass1"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(client, headers, csv: str, *, kind="students", filename="x.csv"):
    files = {"file": (filename, io.BytesIO(csv.encode("utf-8")), "text/csv")}
    return client.post(f"/api/v1/imports/{kind}", files=files, headers=headers)


def test_successful_import_creates_batch_with_row_snapshots(client, db):
    headers = _staff_headers(client, db)
    csv = STUDENT_CSV_HEADER + "S0001,张三,2024,计算机学院,软件工程,软工2401\n"
    r = _upload(client, headers, csv, filename="stu1.csv")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 1
    assert body["batch_id"] and body["status"] == "completed"

    batch = db.get(ImportBatch, body["batch_id"])
    assert batch.kind == "students"
    assert batch.filename == "stu1.csv"
    assert batch.created_count == 1
    assert batch.total_rows == 1

    rows = list(db.scalars(select(ImportBatchRow).where(ImportBatchRow.batch_id == batch.id)))
    assert len(rows) == 1
    assert rows[0].op == "create"
    assert rows[0].table_name == "students"
    assert rows[0].record_pk is not None


def test_update_path_records_before_snapshot(client, db):
    headers = _staff_headers(client, db, username="batch_staff_upd")
    csv = STUDENT_CSV_HEADER + "S0002,李四,2024,计算机学院,软件工程,软工2401\n"
    _upload(client, headers, csv)
    # 第二次上传，同学号但变更专业
    csv2 = STUDENT_CSV_HEADER + "S0002,李四,2024,计算机学院,人工智能,AI2401\n"
    r2 = _upload(client, headers, csv2, filename="stu_upd.csv")
    body = r2.json()
    assert body["updated"] == 1

    db.expire_all()
    student = db.scalar(select(Student).where(Student.student_no == "S0002"))
    assert student.major == "人工智能"

    batch = db.get(ImportBatch, body["batch_id"])
    rows = list(db.scalars(select(ImportBatchRow).where(ImportBatchRow.batch_id == batch.id)))
    assert len(rows) == 1
    assert rows[0].op == "update"
    # before 快照应保留旧 major
    assert rows[0].before is not None
    assert rows[0].before["major"] == "软件工程"
    assert rows[0].before["class_name"] == "软工2401"


def test_all_failed_marks_batch_rolled_back_and_no_business_writes(client, db):
    headers = _staff_headers(client, db, username="batch_staff_fail")
    # 缺必填 enroll_year
    csv = STUDENT_CSV_HEADER + "S0003,王五,,计算机学院,软件工程,软工2401\n"
    r = _upload(client, headers, csv, filename="bad.csv")
    body = r.json()
    assert body["created"] == 0
    assert len(body["errors"]) == 1
    batch = db.get(ImportBatch, body["batch_id"])
    assert batch.status == "rolled_back"
    # 无 Student 落库
    assert db.scalar(select(Student).where(Student.student_no == "S0003")) is None


def test_list_batches_filter_and_detail(client, db):
    headers = _staff_headers(client, db, username="batch_query")
    # 造一条历史
    csv = STUDENT_CSV_HEADER + "S0010,赵六,2024,计算机学院,软件工程,软工2401\n"
    upload = _upload(client, headers, csv, filename="q.csv")
    bid = upload.json()["batch_id"]

    r = client.get("/api/v1/imports/batches?kind=students&page=1&size=10", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert all(i["kind"] == "students" for i in body["items"])

    r2 = client.get(f"/api/v1/imports/batches/{bid}", headers=headers)
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["id"] == bid
    assert detail["filename"] == "q.csv"
    # errors 字段在 detail 中存在（即便为空）
    assert "errors" in detail

from __future__ import annotations

import io
import json

from sqlalchemy import select

from app.models.student import Student
from tests.conftest import make_user


def _staff(client, db, *, username):
    make_user(db, role="counselor", username=username, password="GoodPass1")
    db.commit()
    r = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "GoodPass1"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_mapping_crud(client, db):
    headers = _staff(client, db, username="map_crud")
    payload = {
        "kind": "students",
        "name": "教务处导出",
        "mapping": {"学号": "student_no", "姓名": "name", "入学年份": "enroll_year"},
        "is_default": True,
    }
    r = client.post("/api/v1/imports/mappings", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    mid = r.json()["id"]

    # 重名 409
    r2 = client.post("/api/v1/imports/mappings", json=payload, headers=headers)
    assert r2.status_code == 409

    # 列表 + kind 过滤
    listed = client.get("/api/v1/imports/mappings?kind=students", headers=headers).json()
    assert any(m["id"] == mid for m in listed)

    # 更新
    r3 = client.put(f"/api/v1/imports/mappings/{mid}", json={"name": "教务处导出v2"}, headers=headers)
    assert r3.status_code == 200 and r3.json()["name"] == "教务处导出v2"

    # 删除
    r4 = client.delete(f"/api/v1/imports/mappings/{mid}", headers=headers)
    assert r4.status_code == 200
    assert all(m["id"] != mid for m in client.get("/api/v1/imports/mappings", headers=headers).json())


def test_chinese_header_csv_imported_via_mapping_template(client, db):
    headers = _staff(client, db, username="map_use")
    # 创建模板
    create = client.post(
        "/api/v1/imports/mappings",
        json={
            "kind": "students",
            "name": "标准中文",
            "mapping": {
                "学号": "student_no", "姓名": "name", "入学年份": "enroll_year",
                "学院": "college", "专业": "major", "班级": "class_name",
            },
        },
        headers=headers,
    ).json()
    mid = create["id"]

    csv = "学号,姓名,入学年份,学院,专业,班级\nC0001,陈一,2024,信息学院,大数据,数据2401\n"
    files = {"file": ("zh.csv", io.BytesIO(csv.encode("utf-8")), "text/csv")}
    r = client.post(
        "/api/v1/imports/students",
        files=files,
        data={"mapping_id": str(mid)},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1
    assert db.scalar(select(Student).where(Student.student_no == "C0001")) is not None


def test_inline_mapping_json(client, db):
    headers = _staff(client, db, username="map_inline")
    csv = "stu_id,full_name,year,col,maj,cls\nI0001,英特,2024,A,B,C\n"
    files = {"file": ("inline.csv", io.BytesIO(csv.encode("utf-8")), "text/csv")}
    mapping = {
        "stu_id": "student_no", "full_name": "name", "year": "enroll_year",
        "col": "college", "maj": "major", "cls": "class_name",
    }
    r = client.post(
        "/api/v1/imports/students",
        files=files,
        data={"mapping": json.dumps(mapping)},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1


def test_mapping_id_type_mismatch_400(client, db):
    headers = _staff(client, db, username="map_mismatch")
    create = client.post(
        "/api/v1/imports/mappings",
        json={"kind": "courses", "name": "课程模板", "mapping": {"编码": "code"}},
        headers=headers,
    ).json()
    files = {"file": ("x.csv", io.BytesIO(b"any\n"), "text/csv")}
    r = client.post(
        "/api/v1/imports/students",
        files=files,
        data={"mapping_id": str(create["id"])},
        headers=headers,
    )
    assert r.status_code == 400

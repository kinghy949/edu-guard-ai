from __future__ import annotations

from decimal import Decimal

from app.models.grade import GradeStatus
from app.models.warning_rule import WarningRuleORM
from app.services.warning_engine import generate_for_student, load_rule_for_student
from tests.conftest import make_course, make_grade, make_program_with_buckets, make_student, make_user


def _login(client, username, pwd="GoodPass1"):
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": pwd},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _admin(client, db, *, username):
    make_user(db, role="admin", username=username, password="GoodPass1")
    db.commit()
    r = _login(client, username)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_crud_and_invalid_threshold(client, db):
    headers = _admin(client, db, username="wr_crud")
    # 创建
    r = client.post("/api/v1/admin/warning-rules", json={
        "name": "信息学院严格",
        "scope_college": "信息学院",
        "severe_total_gap_ratio": 0.4,
        "warn_total_gap_ratio": 0.2,
        "severe_required_ratio": 0.6,
        "warn_category_ratio": 0.8,
        "required_category_keywords": ["必修", "核心"],
        "stage_total_semesters": 8,
        "priority": 5,
    }, headers=headers)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]

    # 列表
    items = client.get("/api/v1/admin/warning-rules", headers=headers).json()
    assert any(i["id"] == rid for i in items)

    # 非法阈值 (>1) 应 422
    bad = client.post("/api/v1/admin/warning-rules", json={
        "name": "bad", "severe_total_gap_ratio": 1.5,
    }, headers=headers)
    assert bad.status_code == 422

    # PATCH
    r2 = client.patch(f"/api/v1/admin/warning-rules/{rid}",
                      json={"warn_total_gap_ratio": 0.3}, headers=headers)
    assert r2.status_code == 200 and r2.json()["warn_total_gap_ratio"] == 0.3

    # DELETE 非全局规则可删
    r3 = client.delete(f"/api/v1/admin/warning-rules/{rid}", headers=headers)
    assert r3.status_code == 200


def test_load_rule_major_over_college_over_global(client, db):
    _admin(client, db, username="wr_match")
    program, _ = make_program_with_buckets(db)
    student = make_student(db, student_no="W0001", program=program,
                           college="信息学院", major="软件工程")
    db.commit()

    # 默认情况下：无规则 → DEFAULT_RULE
    rule, rid = load_rule_for_student(db, student)
    assert rid is None
    default_severe = rule.severe_total_gap_ratio

    # 全局规则
    g = WarningRuleORM(name="g", severe_total_gap_ratio=0.45, priority=1)
    db.add(g)
    # 学院规则
    c = WarningRuleORM(name="c", scope_college="信息学院", severe_total_gap_ratio=0.40, priority=1)
    db.add(c)
    # 专业规则
    m = WarningRuleORM(name="m", scope_major="软件工程", severe_total_gap_ratio=0.30, priority=1)
    db.add(m)
    db.commit()
    db.refresh(g)
    db.refresh(c)
    db.refresh(m)

    rule, rid = load_rule_for_student(db, student)
    assert rid == m.id
    assert rule.severe_total_gap_ratio == 0.30

    # 删除专业规则后命中学院
    db.delete(m)
    db.commit()
    rule, rid = load_rule_for_student(db, student)
    assert rid == c.id

    # 再删学院后命中全局
    db.delete(c)
    db.commit()
    rule, rid = load_rule_for_student(db, student)
    assert rid == g.id
    # 与早先 DEFAULT_RULE 不同（确认 DB 规则确实起作用）
    assert rule.severe_total_gap_ratio != default_severe


def test_global_rule_threshold_changes_affect_generation(client, db):
    _admin(client, db, username="wr_gen")
    program, buckets = make_program_with_buckets(
        db, total_credits="20",
        buckets=[("必修", "10"), ("选修", "10")],
    )
    # 学生完成 8 / 20 = 40%，缺口 60% → 在 stage=8 时触发 severe（缺口 > 0.5）
    student = make_student(db, student_no="W0002", program=program, enroll_year=2020)
    req_course = make_course(db, code="CS_R1", name="必修1", credits="8",
                             bucket=buckets[0], program=program, is_required=True)
    make_grade(db, student=student, course=req_course, credits_earned="8",
               score="80", status=GradeStatus.COMPLETED)
    db.commit()

    # 默认 DEFAULT_RULE（无任何 DB 规则）→ 严重
    w1 = generate_for_student(db, student, semester="2024-1", persist=False)
    assert w1 and w1.level == "severe"

    # 写入一条极宽松全局规则：阈值置 1 / 0 让严重和警告均不触发，
    # 但 total_gap > 0 仍落到 info
    db.add(WarningRuleORM(
        name="loose", severe_total_gap_ratio=1.0, warn_total_gap_ratio=1.0,
        severe_required_ratio=0.0, warn_category_ratio=0.0,
        required_category_keywords=["必修"], stage_total_semesters=8,
        enabled=True, priority=10,
    ))
    db.commit()
    # 注意：学生无挂科，所以宽松规则下 _evaluate 各分支均不触发；
    # 但 total_gap>0 仍会落到 info 提示
    w2 = generate_for_student(db, student, semester="2024-2", persist=False)
    assert w2 and w2.level == "info"
    # detail 应带 rule_id 追溯
    assert "rule_id" in w2.detail


def test_cannot_delete_last_global_rule(client, db):
    headers = _admin(client, db, username="wr_safeguard")
    # 创建仅有一条全局规则
    r = client.post("/api/v1/admin/warning-rules",
                    json={"name": "唯一全局"}, headers=headers).json()
    # 尝试删除
    bad = client.delete(f"/api/v1/admin/warning-rules/{r['id']}", headers=headers)
    assert bad.status_code == 409

from __future__ import annotations

import pytest

from app.core.password_policy import ensure_password_valid, validate_password


def test_too_short():
    errs = validate_password("Ab1")
    assert any("长度" in e for e in errs)


def test_letters_only_rejected():
    errs = validate_password("Abcdefgh")
    assert any("字母和数字" in e for e in errs)


def test_digits_only_rejected():
    errs = validate_password("12345678")
    assert any("字母和数字" in e for e in errs)


def test_equals_username_rejected():
    errs = validate_password("Student1", username="student1")
    assert any("用户名" in e for e in errs)


def test_equals_student_no_rejected():
    errs = validate_password("20240001", student_no="20240001")
    # 也会因纯数字触发"字母和数字"规则，但学号规则应同时出现
    assert any("学号" in e for e in errs)


def test_unequal_student_no_passes_student_check():
    # 与学号不同时不应触发"学号"规则（其它规则不在本用例关注范围）
    errs = validate_password("StrongPass1", student_no="20240001")
    assert not any("学号" in e for e in errs)


def test_valid_password_passes():
    assert validate_password("StrongPass1", username="alice") == []


def test_ensure_password_valid_raises():
    with pytest.raises(ValueError):
        ensure_password_valid("weak")

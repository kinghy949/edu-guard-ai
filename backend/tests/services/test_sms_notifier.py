from __future__ import annotations

from app.notifiers.sms import SmsNotifier


class _Resp:
    def __init__(self, status_code=200, json_data=None, content_type="application/json"):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = {"content-type": content_type}
        self.text = "raw"

    def json(self):
        return self._json


def test_validate_config_mock_ok():
    assert SmsNotifier().validate_config({"provider": "mock"}) == []


def test_validate_config_aliyun_missing_keys():
    errs = SmsNotifier().validate_config({"provider": "aliyun"})
    assert any("access_key_id" in e for e in errs)
    assert any("template_code" in e for e in errs)


def test_validate_config_unknown_provider():
    errs = SmsNotifier().validate_config({"provider": "twilio"})
    assert any("未知 provider" in e for e in errs)


def test_send_mock_returns_ok():
    out = SmsNotifier().send("13800000000", "", "你好",
                             {"provider": "mock", "template_code": "SMS_001"})
    assert out.ok is True
    assert out.payload["mock"] is True
    assert out.payload["target"] == "13800000000"


def test_send_aliyun_signature_request(monkeypatch):
    captured = {}

    def fake_post(url, data, timeout):
        captured["url"] = url
        captured["data"] = data
        return _Resp(json_data={"Code": "OK", "BizId": "xx"})

    monkeypatch.setattr("app.notifiers.sms.httpx.post", fake_post)
    cfg = {
        "provider": "aliyun",
        "access_key_id": "AKID",
        "access_key_secret": "SECRET",
        "sign_name": "EduGuard",
        "template_code": "SMS_PASS",
        "template_param": {"name": "张三"},
    }
    out = SmsNotifier().send("13912340000", "", "ignored", cfg)
    assert out.ok is True
    assert captured["url"].startswith("https://dysmsapi.aliyuncs.com")
    payload = captured["data"]
    assert payload["Action"] == "SendSms"
    assert payload["PhoneNumbers"] == "13912340000"
    assert payload["SignName"] == "EduGuard"
    assert payload["TemplateCode"] == "SMS_PASS"
    # 签名相关字段必须出现
    assert payload["SignatureMethod"] == "HMAC-SHA1"
    assert payload["SignatureVersion"] == "1.0"
    assert payload["AccessKeyId"] == "AKID"
    assert "Signature" in payload and payload["Signature"]
    # TemplateParam 应序列化
    assert "张三" in payload["TemplateParam"]


def test_send_aliyun_returns_failed_on_non_ok(monkeypatch):
    def fake_post(url, data, timeout):
        return _Resp(json_data={"Code": "isv.BUSINESS_LIMIT_CONTROL", "Message": "频繁"})

    monkeypatch.setattr("app.notifiers.sms.httpx.post", fake_post)
    out = SmsNotifier().send("13912340000", "", "x",
                             {"provider": "aliyun", "access_key_id": "k",
                              "access_key_secret": "s", "sign_name": "n",
                              "template_code": "T"})
    assert out.ok is False
    assert "BUSINESS_LIMIT_CONTROL" in out.detail or "isv" in out.detail

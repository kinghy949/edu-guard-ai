"""短信渠道。

支持两种 provider：
- ``mock``：仅记录日志、返回 ok，便于本地/试点演示；payload 含 mock=True
- ``aliyun``：调用阿里云短信 V3 接口（HMAC-SHA256 签名），不引入 SDK
  直接用 httpx 调 /dysmsapi/SendSms.json

config（aliyun 需全部填）:
  provider: "mock" | "aliyun"  默认 mock
  access_key_id
  access_key_secret
  sign_name
  template_code
  template_param: dict 可选，作为 TemplateParam JSON
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.logging import get_logger
from app.notifiers.base import SendOutcome

log = get_logger("notify.sms")

_REQUIRED_BY_PROVIDER = {
    "mock": [],
    "aliyun": ["access_key_id", "access_key_secret", "sign_name", "template_code"],
}


class SmsNotifier:
    channel = "sms"

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        provider = (config.get("provider") or "mock").lower()
        if provider not in _REQUIRED_BY_PROVIDER:
            return [f"未知 provider: {provider}（mock | aliyun）"]
        missing = [k for k in _REQUIRED_BY_PROVIDER[provider] if not config.get(k)]
        return [f"SMS 配置缺少 {k}" for k in missing]

    def send(self, target: str, subject: str, content: str, config: dict[str, Any]) -> SendOutcome:
        errs = self.validate_config(config)
        if errs:
            return SendOutcome(ok=False, detail="；".join(errs))
        provider = (config.get("provider") or "mock").lower()
        if provider == "mock":
            log.info("sms_mock_send", target=target, template_code=config.get("template_code"))
            return SendOutcome(
                ok=True, detail="sms mock",
                payload={"target": target, "template_code": config.get("template_code"), "mock": True},
            )
        return _send_aliyun(target, content, config)


def _send_aliyun(target: str, content: str, cfg: dict[str, Any]) -> SendOutcome:
    """阿里云短信 V1 旧 RPC 风格（POPAPI，HMAC-SHA1 + Base64）。

    实现参考：https://help.aliyun.com/document_detail/101343.html
    """
    endpoint = cfg.get("endpoint") or "https://dysmsapi.aliyuncs.com"
    params: dict[str, str] = {
        "Format": "JSON",
        "Version": "2017-05-25",
        "AccessKeyId": cfg["access_key_id"],
        "SignatureMethod": "HMAC-SHA1",
        "SignatureVersion": "1.0",
        "SignatureNonce": secrets.token_hex(16),
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Action": "SendSms",
        "PhoneNumbers": target,
        "SignName": cfg["sign_name"],
        "TemplateCode": cfg["template_code"],
    }
    template_param = cfg.get("template_param")
    if template_param:
        params["TemplateParam"] = (
            template_param if isinstance(template_param, str) else json.dumps(template_param, ensure_ascii=False)
        )

    canonical = "&".join(
        f"{_quote(k)}={_quote(v)}"
        for k, v in sorted(params.items())
    )
    string_to_sign = "POST&%2F&" + _quote(canonical)
    signing_key = (cfg["access_key_secret"] + "&").encode("utf-8")
    digest = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    signature = base64.b64encode(digest).decode("ascii")
    params["Signature"] = signature

    try:
        r = httpx.post(endpoint, data=params, timeout=15)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text}
    except httpx.HTTPError as e:
        return SendOutcome(ok=False, detail=f"阿里云请求失败: {e}")
    if r.status_code == 200 and (data.get("Code") == "OK"):
        return SendOutcome(ok=True, detail="aliyun OK", payload={"BizId": data.get("BizId")})
    return SendOutcome(ok=False, detail=f"阿里云返回失败: {data}", payload=data)


def _quote(s: str) -> str:
    return urllib.parse.quote(str(s), safe="-_.~")

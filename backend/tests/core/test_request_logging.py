from __future__ import annotations


def test_request_id_returned_in_header(client):
    r = client.get("/health")
    assert r.status_code == 200
    rid = r.headers.get("X-Request-ID")
    assert rid and len(rid) >= 8


def test_request_id_passthrough_when_supplied(client):
    custom = "fixedrid001234"
    r = client.get("/health", headers={"X-Request-ID": custom})
    assert r.headers.get("X-Request-ID") == custom

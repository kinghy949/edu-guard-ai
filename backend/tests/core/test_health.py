from __future__ import annotations

from app import __version__


def test_health_reports_version_and_db_status(client):
    r = client.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": __version__, "db": "ok"}


def test_health_returns_503_when_db_unavailable(client, monkeypatch):
    def broken_session_local():
        raise RuntimeError("db down")

    monkeypatch.setattr("app.main.SessionLocal", broken_session_local)

    r = client.get("/health")

    assert r.status_code == 503
    assert r.json() == {"status": "error", "version": __version__, "db": "error"}

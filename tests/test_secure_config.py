import pytest

from app.secure import create_app


def test_production_runtime_requires_explicit_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="APP_SECRET_KEY must be explicitly configured"):
        create_app("sqlite+pysqlite:///:memory:")


def test_production_runtime_rejects_known_development_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "development-only-change-me")

    with pytest.raises(RuntimeError, match="APP_SECRET_KEY must be explicitly configured"):
        create_app("sqlite+pysqlite:///:memory:")


def test_production_runtime_accepts_explicit_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "a-production-secret-with-sufficient-entropy-for-testing")

    app = create_app("sqlite+pysqlite:///:memory:", auth_required=False)
    assert app.config["SECRET_KEY"] == "a-production-secret-with-sufficient-entropy-for-testing"

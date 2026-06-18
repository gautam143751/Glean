from __future__ import annotations

from glean_folder_ingest.config import load_config


def test_load_local_config(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_TYPE", "local")
    monkeypatch.setenv("LOCAL_FOLDER", "/tmp/docs")
    monkeypatch.setenv("GLEAN_API_TOKEN", "token")
    monkeypatch.setenv("GLEAN_SERVER_URL", "https://customer-be.glean.com")
    monkeypatch.setenv("GLEAN_DATASOURCE", "local-folder-docs")
    monkeypatch.setenv("GLEAN_VIEW_URL_BASE", "https://viewer.example.com/docs")
    monkeypatch.setenv("GLEAN_DEFAULT_ALLOWED_USERS", "a@example.com,b@example.com")

    config = load_config()

    assert config.source.source_type == "local"
    assert str(config.source.local_folder) == "/tmp/docs"
    assert config.glean.default_allowed_users == ["a@example.com", "b@example.com"]

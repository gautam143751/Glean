from __future__ import annotations

import pytest

from glean_folder_ingest.config import ConfigError, load_config


def test_load_local_config(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_TYPE", "local")
    monkeypatch.setenv("LOCAL_FOLDER", "/tmp/docs")
    monkeypatch.setenv("GLEAN_API_TOKEN", "token")
    monkeypatch.setenv("GLEAN_SERVER_URL", "https://customer-be.glean.com")
    monkeypatch.setenv("GLEAN_DATASOURCE", "localfolderdocs")
    monkeypatch.setenv("GLEAN_VIEW_URL_BASE", "https://viewer.example.com/docs")
    monkeypatch.setenv("GLEAN_DEFAULT_ALLOWED_USERS", "a@example.com,b@example.com")

    config = load_config()

    assert config.source.source_type == "local"
    assert str(config.source.local_folder) == "/tmp/docs"
    assert config.glean.default_allowed_users == ["a@example.com", "b@example.com"]


def test_load_config_rejects_non_alphanumeric_datasource(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_TYPE", "local")
    monkeypatch.setenv("LOCAL_FOLDER", "/tmp/docs")
    monkeypatch.setenv("GLEAN_API_TOKEN", "token")
    monkeypatch.setenv("GLEAN_SERVER_URL", "https://customer-be.glean.com")
    monkeypatch.setenv("GLEAN_DATASOURCE", "local-folder-docs")
    monkeypatch.setenv("GLEAN_VIEW_URL_BASE", "https://viewer.example.com/docs")

    with pytest.raises(ConfigError, match="alphanumeric"):
        load_config()


def test_load_config_rejects_regex_view_url_base(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_TYPE", "local")
    monkeypatch.setenv("LOCAL_FOLDER", "/tmp/docs")
    monkeypatch.setenv("GLEAN_API_TOKEN", "token")
    monkeypatch.setenv("GLEAN_SERVER_URL", "https://customer-be.glean.com")
    monkeypatch.setenv("GLEAN_DATASOURCE", "localfolderdocs")
    monkeypatch.setenv("GLEAN_VIEW_URL_BASE", "https://viewer.example.com/.*")

    with pytest.raises(ConfigError, match="concrete URL"):
        load_config()

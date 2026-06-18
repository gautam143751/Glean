from __future__ import annotations

from glean_folder_ingest.config import GleanConfig
from glean_folder_ingest.glean_client import GleanClient


def test_setup_datasource_payload_includes_object_and_properties(monkeypatch) -> None:
    config = GleanConfig(
        api_token="token",
        server_url="https://customer-be.glean.com",
        datasource="local-folder-docs",
        display_name="Local Folder Docs",
        datasource_category="PUBLISHED_CONTENT",
        object_type="LocalFile",
        view_url_base="https://viewer.example.com/docs",
        default_allowed_users=["user@example.com"],
        allow_anonymous_access=False,
    )
    captured = {}

    def fake_post(self, path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {"ok": True}

    monkeypatch.setattr(GleanClient, "_post", fake_post)

    response = GleanClient(config).setup_datasource()

    assert response == {"ok": True}
    assert captured["path"] == "/api/index/v1/adddatasource"
    object_definition = captured["payload"]["objectDefinitions"][0]
    assert object_definition["name"] == "LocalFile"
    assert {item["name"] for item in object_definition["propertyDefinitions"]} == {
        "source_uri",
        "source_size_bytes",
    }


def test_get_datasource_config_uses_requested_datasource(monkeypatch) -> None:
    config = GleanConfig(
        api_token="token",
        server_url="https://customer-be.glean.com",
        datasource="local-folder-docs",
        display_name="Local Folder Docs",
        datasource_category="PUBLISHED_CONTENT",
        object_type="LocalFile",
        view_url_base="https://viewer.example.com/docs",
        default_allowed_users=["user@example.com"],
        allow_anonymous_access=False,
    )
    captured = {}

    def fake_post(self, path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {"datasource": "other-docs"}

    monkeypatch.setattr(GleanClient, "_post", fake_post)

    response = GleanClient(config).get_datasource_config("other-docs")

    assert response == {"datasource": "other-docs"}
    assert captured == {
        "path": "/api/index/v1/getdatasourceconfig",
        "payload": {"datasource": "other-docs"},
    }

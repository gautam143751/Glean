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
        "sourceuri",
        "sourcesizebytes",
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


def test_index_documents_payload_matches_glean_schema(monkeypatch) -> None:
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

    document = {
        "datasource": "local-folder-docs",
        "objectType": "LocalFile",
        "id": "abc123",
        "title": "notes.txt",
        "body": {"mimeType": "text/plain", "textContent": "hello"},
        "permissions": {"allowedUsers": [{"email": "user@example.com"}]},
        "viewURL": "https://viewer.example.com/docs/abc123",
    }

    response = GleanClient(config).index_documents([document])

    assert response == {"ok": True}
    assert captured == {
        "path": "/api/index/v1/indexdocuments",
        "payload": {
            "datasource": "local-folder-docs",
            "documents": [document],
        },
    }


def test_index_user_payload_matches_glean_schema(monkeypatch) -> None:
    config = GleanConfig(
        api_token="token",
        server_url="https://customer-be.glean.com",
        datasource="localfolderdocs",
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

    response = GleanClient(config).index_user("user@example.com")

    assert response == {"ok": True}
    assert captured == {
        "path": "/api/index/v1/indexuser",
        "payload": {
            "datasource": "localfolderdocs",
            "user": {
                "email": "user@example.com",
                "name": "user",
                "isActive": True,
            },
        },
    }

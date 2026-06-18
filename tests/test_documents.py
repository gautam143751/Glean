from __future__ import annotations

from glean_folder_ingest.config import GleanConfig
from glean_folder_ingest.documents import (
    SourceDocument,
    is_supported_mime_type,
    source_document_from_bytes,
    stable_document_id,
    to_glean_document,
)


def test_stable_document_id_is_alphanumeric() -> None:
    doc_id = stable_document_id("file:///tmp/example doc.md")

    assert doc_id.isalnum()
    assert doc_id == stable_document_id("file:///tmp/example doc.md")


def test_supported_mime_type_filters_unsupported_media() -> None:
    assert is_supported_mime_type("text/plain")
    assert is_supported_mime_type("application/pdf")
    assert not is_supported_mime_type("image/png")
    assert not is_supported_mime_type("application/json")


def test_to_glean_document_uses_allowed_users() -> None:
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
    source = SourceDocument(
        uri="file:///tmp/example.md",
        name="example.md",
        mime_type="text/markdown",
        content=b"# Hello",
        size=7,
    )

    document = to_glean_document(source, config)

    assert document["datasource"] == "local-folder-docs"
    assert document["objectType"] == "LocalFile"
    assert document["permissions"] == {"allowedUsers": [{"email": "user@example.com"}]}
    assert document["body"] == {"mimeType": "text/markdown", "textContent": "# Hello"}


def test_source_document_from_bytes_falls_back_to_name_mime_type() -> None:
    source = source_document_from_bytes("notes.md", b"# Notes", "application/octet-stream")

    assert source.mime_type == "text/markdown"
    assert source.uri.startswith("upload://manual-upload/notes.md/")

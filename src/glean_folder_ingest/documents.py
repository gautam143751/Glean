from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import mimetypes
from pathlib import Path
import re
from typing import Protocol

from .config import GleanConfig, SourceConfig


SUPPORTED_TEXT_MIME_TYPES = {
    "text/csv",
    "text/html",
    "text/markdown",
    "text/plain",
    "text/tab-separated-values",
    "text/vcard",
}

SUPPORTED_BINARY_MIME_TYPES = {
    "application/epub+zip",
    "application/msword",
    "application/onenote",
    "application/pdf",
    "application/rtf",
    "application/vnd.apple.keynote",
    "application/vnd.apple.pages",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.site",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/x-apple-diskimage",
    "application/x-executable",
}

UNSUPPORTED_PREFIXES = ("audio/", "image/", "video/")
UNSUPPORTED_MIME_TYPES = {
    "application/json",
    "application/mp4",
    "application/rar",
    "application/xml",
    "application/zip",
    "text/css",
    "text/xml",
}


@dataclass(frozen=True)
class SourceDocument:
    uri: str
    name: str
    mime_type: str
    content: bytes
    size: int
    updated_at: int | None = None


class SourceReader(Protocol):
    def iter_documents(self) -> list[SourceDocument]:
        ...


def infer_mime_type(name: str) -> str:
    mime_type, _ = mimetypes.guess_type(name)
    return mime_type or "text/plain"


def is_supported_mime_type(mime_type: str) -> bool:
    if mime_type in UNSUPPORTED_MIME_TYPES:
        return False
    if mime_type.startswith(UNSUPPORTED_PREFIXES):
        return False
    return mime_type in SUPPORTED_TEXT_MIME_TYPES or mime_type in SUPPORTED_BINARY_MIME_TYPES


def stable_document_id(uri: str) -> str:
    digest = hashlib.sha256(uri.encode("utf-8")).digest()
    encoded = base64.b32encode(digest).decode("ascii").rstrip("=")
    return re.sub(r"[^A-Z2-7]", "", encoded).lower()[:48]


def build_view_url(view_url_base: str, document_id: str) -> str:
    return f"{view_url_base.rstrip('/')}/{document_id}"


def content_body(source_doc: SourceDocument) -> dict[str, str]:
    if source_doc.mime_type in SUPPORTED_TEXT_MIME_TYPES:
        return {
            "mimeType": source_doc.mime_type,
            "textContent": source_doc.content.decode("utf-8", errors="replace"),
        }
    return {
        "mimeType": source_doc.mime_type,
        "binaryContent": base64.b64encode(source_doc.content).decode("ascii"),
    }


def to_glean_document(source_doc: SourceDocument, glean: GleanConfig) -> dict:
    document_id = stable_document_id(source_doc.uri)
    permissions: dict[str, object]
    if glean.allow_anonymous_access:
        permissions = {"allowAnonymousAccess": True}
    elif glean.default_allowed_users:
        permissions = {"allowedUsers": [{"email": email} for email in glean.default_allowed_users]}
    else:
        permissions = {"allowAnonymousAccess": False}

    document = {
        "datasource": glean.datasource,
        "objectType": glean.object_type,
        "id": document_id,
        "title": source_doc.name,
        "body": content_body(source_doc),
        "permissions": permissions,
        "viewURL": build_view_url(glean.view_url_base, document_id),
        "customProperties": [
            {"name": "sourceuri", "value": source_doc.uri},
            {"name": "sourcesizebytes", "value": str(source_doc.size)},
        ],
    }
    if source_doc.updated_at:
        document["updatedAt"] = source_doc.updated_at
    return document


def source_document_from_bytes(
    name: str,
    content: bytes,
    mime_type: str | None = None,
    uri_namespace: str = "manual-upload",
) -> SourceDocument:
    resolved_mime_type = infer_mime_type(name) if not mime_type or mime_type == "application/octet-stream" else mime_type
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    return SourceDocument(
        uri=f"upload://{uri_namespace.strip('/')}/{name}/{content_hash}",
        name=name,
        mime_type=resolved_mime_type,
        content=content,
        size=len(content),
    )


class LocalFolderReader:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def iter_documents(self) -> list[SourceDocument]:
        if not self.folder.exists():
            raise FileNotFoundError(f"Local folder does not exist: {self.folder}")
        if not self.folder.is_dir():
            raise NotADirectoryError(f"LOCAL_FOLDER is not a directory: {self.folder}")

        documents: list[SourceDocument] = []
        for path in sorted(self.folder.rglob("*")):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.relative_to(self.folder).parts):
                continue
            mime_type = infer_mime_type(path.name)
            if not is_supported_mime_type(mime_type):
                continue
            content = path.read_bytes()
            relative = path.relative_to(self.folder).as_posix()
            documents.append(
                SourceDocument(
                    uri=f"file://{self.folder.resolve().as_posix()}/{relative}",
                    name=path.name,
                    mime_type=mime_type,
                    content=content,
                    size=len(content),
                )
            )
        return documents


class S3Reader:
    def __init__(self, bucket: str, prefix: str = "", region: str | None = None) -> None:
        self.bucket = bucket
        self.prefix = prefix
        self.region = region

    def iter_documents(self) -> list[SourceDocument]:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("S3 ingestion requires boto3. Install with: python -m pip install -e '.[s3]'") from exc

        kwargs = {"region_name": self.region} if self.region else {}
        client = boto3.client("s3", **kwargs)
        paginator = client.get_paginator("list_objects_v2")
        documents: list[SourceDocument] = []

        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for item in page.get("Contents", []):
                key = item["Key"]
                if key.endswith("/"):
                    continue
                mime_type = infer_mime_type(key)
                if not is_supported_mime_type(mime_type):
                    continue
                obj = client.get_object(Bucket=self.bucket, Key=key)
                content = obj["Body"].read()
                documents.append(
                    SourceDocument(
                        uri=f"s3://{self.bucket}/{key}",
                        name=Path(key).name,
                        mime_type=mime_type,
                        content=content,
                        size=len(content),
                        updated_at=int(item["LastModified"].timestamp()) if item.get("LastModified") else None,
                    )
                )
        return documents


def build_reader(source: SourceConfig) -> SourceReader:
    if source.source_type == "local":
        assert source.local_folder is not None
        return LocalFolderReader(source.local_folder)
    assert source.s3_bucket is not None
    return S3Reader(source.s3_bucket, source.s3_prefix, source.aws_region)

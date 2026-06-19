from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re


class ConfigError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _csv_env(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class SourceConfig:
    source_type: str
    local_folder: Path | None
    s3_bucket: str | None
    s3_prefix: str
    aws_region: str | None


@dataclass(frozen=True)
class GleanConfig:
    api_token: str
    server_url: str
    datasource: str
    display_name: str
    datasource_category: str
    object_type: str
    view_url_base: str
    default_allowed_users: list[str]
    allow_anonymous_access: bool


@dataclass(frozen=True)
class AppConfig:
    glean: GleanConfig
    source: SourceConfig
    upload_batch_size: int
    upload_mode: str
    status_poll_seconds: int
    http_timeout_seconds: int
    max_retries: int


def load_config() -> AppConfig:
    load_dotenv()

    source_type = os.getenv("SOURCE_TYPE", "local").strip().lower()
    if source_type not in {"local", "s3"}:
        raise ConfigError("SOURCE_TYPE must be either 'local' or 's3'")

    local_folder = None
    s3_bucket = None
    if source_type == "local":
        local_folder_raw = os.getenv("LOCAL_FOLDER")
        if not local_folder_raw:
            raise ConfigError("LOCAL_FOLDER is required when SOURCE_TYPE=local")
        local_folder = Path(local_folder_raw).expanduser()
    else:
        s3_bucket = os.getenv("S3_BUCKET")
        if not s3_bucket:
            raise ConfigError("S3_BUCKET is required when SOURCE_TYPE=s3")

    api_token = os.getenv("GLEAN_API_TOKEN")
    if not api_token:
        raise ConfigError("GLEAN_API_TOKEN is required")

    server_url = os.getenv("GLEAN_SERVER_URL", "").rstrip("/")
    if not server_url.startswith("https://"):
        raise ConfigError("GLEAN_SERVER_URL must be an https:// URL")

    datasource = os.getenv("GLEAN_DATASOURCE")
    if not datasource:
        raise ConfigError("GLEAN_DATASOURCE is required")
    if not re.fullmatch(r"[A-Za-z0-9]+", datasource):
        raise ConfigError("GLEAN_DATASOURCE must contain alphanumeric characters only")

    view_url_base = os.getenv("GLEAN_VIEW_URL_BASE", "").rstrip("/")
    if not view_url_base.startswith("http://") and not view_url_base.startswith("https://"):
        raise ConfigError("GLEAN_VIEW_URL_BASE must be an http:// or https:// URL")
    if "*" in view_url_base:
        raise ConfigError("GLEAN_VIEW_URL_BASE must be a concrete URL base, not a regex")

    upload_mode = os.getenv("UPLOAD_MODE", "incremental").strip().lower()
    if upload_mode not in {"incremental", "bulk"}:
        raise ConfigError("UPLOAD_MODE must be either 'incremental' or 'bulk'")

    batch_size = _int_env("UPLOAD_BATCH_SIZE", 50)
    if batch_size < 1:
        raise ConfigError("UPLOAD_BATCH_SIZE must be positive")

    return AppConfig(
        glean=GleanConfig(
            api_token=api_token,
            server_url=server_url,
            datasource=datasource,
            display_name=os.getenv("GLEAN_DATASOURCE_DISPLAY_NAME", datasource),
            datasource_category=os.getenv("GLEAN_DATASOURCE_CATEGORY", "PUBLISHED_CONTENT"),
            object_type=os.getenv("GLEAN_OBJECT_TYPE", "LocalFile"),
            view_url_base=view_url_base,
            default_allowed_users=_csv_env("GLEAN_DEFAULT_ALLOWED_USERS"),
            allow_anonymous_access=_bool_env("GLEAN_ALLOW_ANONYMOUS_ACCESS", False),
        ),
        source=SourceConfig(
            source_type=source_type,
            local_folder=local_folder,
            s3_bucket=s3_bucket,
            s3_prefix=os.getenv("S3_PREFIX", ""),
            aws_region=os.getenv("AWS_REGION") or None,
        ),
        upload_batch_size=batch_size,
        upload_mode=upload_mode,
        status_poll_seconds=_int_env("STATUS_POLL_SECONDS", 0),
        http_timeout_seconds=_int_env("HTTP_TIMEOUT_SECONDS", 60),
        max_retries=_int_env("MAX_RETRIES", 4),
    )

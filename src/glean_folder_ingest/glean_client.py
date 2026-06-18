from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from .config import GleanConfig


class GleanApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class GleanClient:
    config: GleanConfig
    timeout_seconds: int = 60
    max_retries: int = 4

    def setup_datasource(self) -> dict[str, Any]:
        payload = {
            "name": self.config.datasource,
            "displayName": self.config.display_name,
            "datasourceCategory": self.config.datasource_category,
            "urlRegex": f"^{self.config.view_url_base.rstrip('/')}.*",
            "objectDefinitions": [
                {
                    "name": self.config.object_type,
                    "docCategory": self.config.datasource_category,
                    "propertyDefinitions": [
                        {
                            "name": "source_uri",
                            "displayLabel": "Source URI",
                            "displayLabelPlural": "Source URIs",
                            "propertyType": "TEXT",
                            "hideUiFacet": True,
                        },
                        {
                            "name": "source_size_bytes",
                            "displayLabel": "Source Size Bytes",
                            "displayLabelPlural": "Source Size Bytes",
                            "propertyType": "TEXT",
                            "hideUiFacet": True,
                        },
                    ],
                }
            ],
            "isUserReferencedByEmail": True,
        }
        return self._post("/api/index/v1/adddatasource", payload)

    def get_datasource_config(self, datasource: str | None = None) -> dict[str, Any]:
        return self._post(
            "/api/index/v1/getdatasourceconfig",
            {"datasource": datasource or self.config.datasource},
        )

    def index_documents(self, documents: list[dict]) -> dict[str, Any]:
        return self._post(
            "/api/index/v1/indexdocuments",
            {
                "datasource": self.config.datasource,
                "documents": documents,
            },
        )

    def bulk_index_documents(
        self,
        documents: list[dict],
        upload_id: str,
        is_first_page: bool,
        is_last_page: bool,
        force_restart_upload: bool,
    ) -> dict[str, Any]:
        return self._post(
            "/api/index/v1/bulkindexdocuments",
            {
                "uploadId": upload_id,
                "datasource": self.config.datasource,
                "documents": documents,
                "isFirstPage": is_first_page,
                "isLastPage": is_last_page,
                "forceRestartUpload": force_restart_upload,
            },
        )

    def datasource_status(self) -> dict[str, Any]:
        return self._post(f"/api/index/v1/debug/{self.config.datasource}/status", {})

    def documents_info(self, document_ids: list[str]) -> dict[str, Any]:
        return self._post(
            f"/api/index/v1/debug/{self.config.datasource}/documents",
            {"documentIds": document_ids},
        )

    def new_upload_id(self) -> str:
        return f"{self.config.datasource}-{uuid4()}"

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.server_url.rstrip('/')}{path}"
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.config.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except HTTPError as exc:
                if exc.code == 429 and attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                detail = exc.read().decode("utf-8", errors="replace")
                raise GleanApiError(f"Glean API {path} failed with HTTP {exc.code}: {detail}") from exc
            except URLError as exc:
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise GleanApiError(f"Glean API {path} failed: {exc.reason}") from exc

        raise GleanApiError(f"Glean API {path} failed after retries")

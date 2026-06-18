from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Callable

from .config import AppConfig
from .documents import build_reader, to_glean_document
from .glean_client import GleanClient


Progress = Callable[[str], None]


@dataclass(frozen=True)
class IngestResult:
    discovered: int
    uploaded: int
    skipped: int
    mode: str


def chunked(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def upload_glean_documents(
    client: GleanClient,
    documents: list[dict],
    batch_size: int,
    mode: str = "incremental",
    progress: Progress = print,
) -> int:
    if mode not in {"incremental", "bulk"}:
        raise ValueError("mode must be either 'incremental' or 'bulk'")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    batches = chunked(documents, batch_size)
    total_batches = len(batches)
    uploaded = 0

    if mode == "bulk":
        upload_id = client.new_upload_id()
        for index, batch in enumerate(batches, start=1):
            progress(f"Uploading bulk batch {index}/{total_batches}: {len(batch)} document(s)")
            client.bulk_index_documents(
                documents=batch,
                upload_id=upload_id,
                is_first_page=index == 1,
                is_last_page=index == total_batches,
                force_restart_upload=index == 1,
            )
            uploaded += len(batch)
            progress_percent = math.floor((uploaded / len(documents)) * 100) if documents else 100
            progress(f"Uploaded {uploaded}/{len(documents)} document(s), {progress_percent}%")
        return uploaded

    for index, batch in enumerate(batches, start=1):
        progress(f"Uploading incremental batch {index}/{total_batches}: {len(batch)} document(s)")
        client.index_documents(batch)
        uploaded += len(batch)
        progress_percent = math.floor((uploaded / len(documents)) * 100) if documents else 100
        progress(f"Uploaded {uploaded}/{len(documents)} document(s), {progress_percent}%")
    return uploaded


def run_ingest(config: AppConfig, dry_run: bool = False, mode: str | None = None, progress: Progress = print) -> IngestResult:
    upload_mode = mode or config.upload_mode
    if upload_mode not in {"incremental", "bulk"}:
        raise ValueError("mode must be either 'incremental' or 'bulk'")

    progress(f"Discovering documents from {config.source.source_type} source")
    source_documents = build_reader(config.source).iter_documents()
    glean_documents = [to_glean_document(doc, config.glean) for doc in source_documents]
    batches = chunked(glean_documents, config.upload_batch_size)
    total_batches = len(batches)

    progress(f"Prepared {len(glean_documents)} supported documents in {total_batches} batch(es)")
    if dry_run:
        for index, batch in enumerate(batches, start=1):
            progress(f"Dry run batch {index}/{total_batches}: {len(batch)} document(s)")
        return IngestResult(discovered=len(source_documents), uploaded=0, skipped=0, mode=upload_mode)

    client = GleanClient(config.glean, config.http_timeout_seconds, config.max_retries)
    uploaded = upload_glean_documents(
        client=client,
        documents=glean_documents,
        batch_size=config.upload_batch_size,
        mode=upload_mode,
        progress=progress,
    )

    if config.status_poll_seconds > 0:
        progress(f"Waiting {config.status_poll_seconds}s before polling datasource status")
        time.sleep(config.status_poll_seconds)
        status = client.datasource_status()
        progress(f"Datasource status: {status}")

    return IngestResult(discovered=len(source_documents), uploaded=uploaded, skipped=0, mode=upload_mode)

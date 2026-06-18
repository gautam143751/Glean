from __future__ import annotations

from dataclasses import replace
import json
import os
from typing import Any

import streamlit as st

from glean_folder_ingest.config import GleanConfig, load_dotenv
from glean_folder_ingest.documents import is_supported_mime_type, source_document_from_bytes, to_glean_document
from glean_folder_ingest.glean_client import GleanClient
from glean_folder_ingest.ingest import upload_glean_documents


def csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def known_datasources(default_datasource: str) -> list[str]:
    configured = csv_values(os.getenv("GLEAN_KNOWN_DATASOURCES", ""))
    values = [default_datasource, *configured]
    return list(dict.fromkeys([value for value in values if value]))


def build_glean_config(
    api_token: str,
    server_url: str,
    datasource: str,
    display_name: str,
    datasource_category: str,
    object_type: str,
    view_url_base: str,
    allowed_users: str,
    allow_anonymous_access: bool,
) -> GleanConfig:
    return GleanConfig(
        api_token=api_token,
        server_url=server_url.rstrip("/"),
        datasource=datasource.strip(),
        display_name=display_name.strip() or datasource.strip(),
        datasource_category=datasource_category.strip() or "PUBLISHED_CONTENT",
        object_type=object_type.strip() or "LocalFile",
        view_url_base=view_url_base.rstrip("/"),
        default_allowed_users=csv_values(allowed_users),
        allow_anonymous_access=allow_anonymous_access,
    )


def client_for(config: GleanConfig, timeout_seconds: int, max_retries: int) -> GleanClient:
    return GleanClient(config, timeout_seconds=timeout_seconds, max_retries=max_retries)


def render_json(payload: dict[str, Any]) -> None:
    st.code(json.dumps(payload, indent=2, sort_keys=True), language="json")


def uploaded_documents(files: list[Any], config: GleanConfig, namespace: str) -> tuple[list[dict], list[dict]]:
    documents: list[dict] = []
    skipped: list[dict] = []
    for uploaded_file in files:
        mime_type = uploaded_file.type or None
        source_doc = source_document_from_bytes(
            name=uploaded_file.name,
            content=uploaded_file.getvalue(),
            mime_type=mime_type,
            uri_namespace=namespace,
        )
        if not is_supported_mime_type(source_doc.mime_type):
            skipped.append({"name": source_doc.name, "mime_type": source_doc.mime_type, "size": source_doc.size})
            continue
        documents.append(to_glean_document(source_doc, config))
    return documents, skipped


def render_upload_panel(config: GleanConfig, timeout_seconds: int, max_retries: int, batch_size: int) -> None:
    datasources = known_datasources(config.datasource)
    target = st.selectbox("Target datasource", datasources, key="upload_target_datasource")
    object_type = st.text_input("Object type", value=config.object_type, key="upload_object_type")
    namespace = st.text_input("Upload namespace", value="streamlit-upload")
    mode = st.segmented_control("Upload mode", ["incremental", "bulk"], default="incremental")
    target_config = replace(config, datasource=target, object_type=object_type)

    single_tab, batch_tab = st.tabs(["Single File", "Batch Files"])

    with single_tab:
        uploaded_file = st.file_uploader("Choose one file", accept_multiple_files=False, key="single_file")
        if st.button("Push Single File", type="primary", disabled=uploaded_file is None):
            docs, skipped = uploaded_documents([uploaded_file], target_config, namespace)
            if skipped:
                st.warning(f"Skipped unsupported file type: {skipped[0]['name']} ({skipped[0]['mime_type']})")
            if docs:
                with st.status("Uploading file", expanded=True) as status:
                    progress_bar = st.progress(0, text="Starting upload")

                    def progress(message: str) -> None:
                        st.write(message)
                        if message.startswith("Uploaded "):
                            progress_bar.progress(100, text=message)

                    uploaded = upload_glean_documents(
                        client=client_for(target_config, timeout_seconds, max_retries),
                        documents=docs,
                        batch_size=1,
                        mode="incremental",
                        progress=progress,
                    )
                    status.update(label=f"Uploaded {uploaded} file", state="complete")

    with batch_tab:
        uploaded_files = st.file_uploader("Choose files", accept_multiple_files=True, key="batch_files")
        if uploaded_files:
            st.dataframe(
                [{"name": item.name, "mime_type": item.type, "size": item.size} for item in uploaded_files],
                width="stretch",
                hide_index=True,
            )
        if st.button("Push Batch", type="primary", disabled=not uploaded_files):
            docs, skipped = uploaded_documents(uploaded_files, target_config, namespace)
            if skipped:
                st.warning(f"Skipped {len(skipped)} unsupported file(s)")
                st.dataframe(skipped, width="stretch", hide_index=True)
            if docs:
                with st.status("Uploading batch", expanded=True) as status:
                    progress_bar = st.progress(0, text="Starting upload")
                    total = len(docs)

                    def progress(message: str) -> None:
                        st.write(message)
                        if message.startswith("Uploaded "):
                            uploaded_count = int(message.split(" ")[1].split("/")[0])
                            progress_bar.progress(uploaded_count / total, text=message)

                    uploaded = upload_glean_documents(
                        client=client_for(target_config, timeout_seconds, max_retries),
                        documents=docs,
                        batch_size=batch_size,
                        mode=mode,
                        progress=progress,
                    )
                    status.update(label=f"Uploaded {uploaded} file(s)", state="complete")


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="Glean Datasource Uploader", layout="wide")
    st.title("Glean Datasource Uploader")

    with st.sidebar:
        st.header("Connection")
        server_url = st.text_input("Glean server URL", value=os.getenv("GLEAN_SERVER_URL", "https://customer-be.glean.com"))
        api_token = st.text_input("Glean API token", value=os.getenv("GLEAN_API_TOKEN", ""), type="password")
        st.header("Defaults")
        datasource = st.text_input("Datasource", value=os.getenv("GLEAN_DATASOURCE", "local-folder-docs"))
        display_name = st.text_input("Display name", value=os.getenv("GLEAN_DATASOURCE_DISPLAY_NAME", datasource))
        datasource_category = st.text_input("Datasource category", value=os.getenv("GLEAN_DATASOURCE_CATEGORY", "PUBLISHED_CONTENT"))
        object_type = st.text_input("Object type", value=os.getenv("GLEAN_OBJECT_TYPE", "LocalFile"))
        view_url_base = st.text_input("View URL base", value=os.getenv("GLEAN_VIEW_URL_BASE", "https://your-viewer.example.com/docs"))
        allowed_users = st.text_input("Allowed users", value=os.getenv("GLEAN_DEFAULT_ALLOWED_USERS", ""))
        allow_anonymous = st.checkbox(
            "Allow anonymous access",
            value=os.getenv("GLEAN_ALLOW_ANONYMOUS_ACCESS", "").lower() in {"1", "true", "yes", "on"},
        )
        batch_size = st.number_input("Batch size", min_value=1, max_value=100, value=int(os.getenv("UPLOAD_BATCH_SIZE", "50")))
        timeout_seconds = st.number_input("HTTP timeout seconds", min_value=5, max_value=600, value=int(os.getenv("HTTP_TIMEOUT_SECONDS", "60")))
        max_retries = st.number_input("Max retries", min_value=0, max_value=10, value=int(os.getenv("MAX_RETRIES", "4")))

    if not api_token:
        st.info("Enter a Glean API token in the sidebar to call Glean APIs.")

    config = build_glean_config(
        api_token=api_token,
        server_url=server_url,
        datasource=datasource,
        display_name=display_name,
        datasource_category=datasource_category,
        object_type=object_type,
        view_url_base=view_url_base,
        allowed_users=allowed_users,
        allow_anonymous_access=allow_anonymous,
    )

    create_tab, view_tab, upload_tab = st.tabs(["Create Datasource", "View Datasource", "Push Files"])

    with create_tab:
        with st.form("create_datasource_form"):
            st.write("Create or update the configured custom datasource.")
            submitted = st.form_submit_button("Create / Update Datasource", type="primary", disabled=not api_token)
        if submitted:
            try:
                response = client_for(config, timeout_seconds, max_retries).setup_datasource()
                st.success(f"Datasource ready: {config.datasource}")
                render_json(response)
            except Exception as exc:
                st.error(str(exc))

    with view_tab:
        datasources = known_datasources(config.datasource)
        selected = st.selectbox("Datasource", datasources, key="view_target_datasource")
        manual = st.text_input("Or enter datasource name", value=selected)
        col_config, col_status = st.columns(2)
        target_config = replace(config, datasource=manual.strip() or selected)
        with col_config:
            if st.button("Fetch Config", disabled=not api_token):
                try:
                    render_json(client_for(target_config, timeout_seconds, max_retries).get_datasource_config())
                except Exception as exc:
                    st.error(str(exc))
        with col_status:
            if st.button("Fetch Status", disabled=not api_token):
                try:
                    render_json(client_for(target_config, timeout_seconds, max_retries).datasource_status())
                except Exception as exc:
                    st.error(str(exc))

    with upload_tab:
        render_upload_panel(config, timeout_seconds, max_retries, int(batch_size))


if __name__ == "__main__":
    main()

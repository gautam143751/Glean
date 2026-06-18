# Glean Folder Ingest

Python ingestion utility for pushing either a local folder or an S3 prefix into a custom Glean datasource.

It supports:

- Creating/updating a custom datasource with `/api/index/v1/adddatasource`
- Reading documents from a local folder or S3 bucket based on environment config
- Uploading in batches with `/api/index/v1/indexdocuments`
- Optional full replacement mode with `/api/index/v1/bulkindexdocuments`
- Live terminal progress for discovery, upload batches, retries, and status polling
- Optional Glean debug/status checks after upload

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

For S3 support:

```bash
python -m pip install -e ".[s3]"
```

For the Streamlit UI:

```bash
python -m pip install -e ".[ui]"
```

## Configure

Copy `.env.example` to `.env` and fill in values, or export the same variables in your shell.

Required Glean settings:

```bash
GLEAN_API_TOKEN=...
GLEAN_SERVER_URL=https://customer-be.glean.com
GLEAN_DATASOURCE=local-folder-docs
GLEAN_DATASOURCE_DISPLAY_NAME="Local Folder Docs"
GLEAN_OBJECT_TYPE=LocalFile
GLEAN_VIEW_URL_BASE=https://your-viewer.example.com/docs
GLEAN_DEFAULT_ALLOWED_USERS=user@company.com
GLEAN_KNOWN_DATASOURCES=local-folder-docs,another-custom-datasource
```

Local source:

```bash
SOURCE_TYPE=local
LOCAL_FOLDER=/path/to/folder
```

S3 source:

```bash
SOURCE_TYPE=s3
S3_BUCKET=my-bucket
S3_PREFIX=optional/prefix/
AWS_REGION=us-east-1
```

## Run

Create/update the custom datasource:

```bash
glean-ingest setup-datasource
```

Upload documents:

```bash
glean-ingest ingest
```

Dry run without calling Glean:

```bash
glean-ingest ingest --dry-run
```

Full replacement upload using `bulkindexdocuments`:

```bash
glean-ingest ingest --mode bulk
```

Poll datasource status:

```bash
glean-ingest status
```

Launch the Streamlit UI:

```bash
streamlit run src/glean_folder_ingest/streamlit_app.py
```

The UI supports:

- Creating or updating a custom datasource
- Fetching datasource config/status for known or manually entered datasource names
- Uploading one file to an existing datasource
- Uploading multiple files in incremental or bulk mode
- Progress display while batches upload

## Notes

- Normal sync uses `indexdocuments`, which adds or updates documents without deleting other indexed documents.
- `--mode bulk` uses `bulkindexdocuments`, which replaces the datasource corpus. Documents omitted from the latest bulk upload may be deleted asynchronously by Glean.
- Document IDs are stable alphanumeric SHA-256-derived IDs based on source URI.
- JSON, XML, video, image, audio, zip, and rar files are skipped by default because Glean lists those MIME families as unsupported for indexing.
- The Glean token should not be placed in browser-side code. Run this as a CLI, daemon, or backend-side job.

## Useful Commands

```bash
python -m pytest
python -m glean_folder_ingest.cli ingest --dry-run
```

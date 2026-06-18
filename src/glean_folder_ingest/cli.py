from __future__ import annotations

import argparse
import json
import sys

from .config import ConfigError, load_config
from .glean_client import GleanClient
from .ingest import run_ingest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="glean-ingest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup-datasource", help="Create or update the configured custom datasource")

    ingest_parser = subparsers.add_parser("ingest", help="Upload configured source documents into Glean")
    ingest_parser.add_argument("--dry-run", action="store_true", help="Discover and prepare batches without calling Glean")
    ingest_parser.add_argument("--mode", choices=["incremental", "bulk"], help="Override UPLOAD_MODE")

    subparsers.add_parser("status", help="Fetch datasource debug status")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config()
        client = GleanClient(config.glean, config.http_timeout_seconds, config.max_retries)

        if args.command == "setup-datasource":
            response = client.setup_datasource()
            print(json.dumps(response, indent=2, sort_keys=True))
            return 0

        if args.command == "ingest":
            result = run_ingest(config, dry_run=args.dry_run, mode=args.mode)
            print(json.dumps(result.__dict__, indent=2, sort_keys=True))
            return 0

        if args.command == "status":
            response = client.datasource_status()
            print(json.dumps(response, indent=2, sort_keys=True))
            return 0

        parser.error(f"unknown command: {args.command}")
        return 2
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

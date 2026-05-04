from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ABSOLUTE_ROOTS = (PROJECT_ROOT, Path("/tmp"))
DEFAULT_REGISTRY_PATH = Path("metadata/source_registry.yaml")
DEFAULT_DOWNLOAD_LOG_PATH = Path("metadata/download_log.json")


class CollectionError(RuntimeError):
    """Raised for explicit, user-actionable collection failures."""


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )


def safe_project_path(path_value: str | Path) -> Path:
    candidate = Path(path_value)
    resolved = (PROJECT_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"path is outside project root: {path_value}")
    return resolved


def safe_writable_path(path_value: str | Path) -> Path:
    candidate = Path(path_value)
    resolved = (PROJECT_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not any(resolved.is_relative_to(root.resolve()) for root in ALLOWED_ABSOLUTE_ROOTS):
        raise ValueError(f"path is outside allowed writable roots: {path_value}")
    return resolved


def load_source_registry(registry_path: Path) -> dict[str, Any]:
    if not registry_path.is_file():
        raise CollectionError(f"source registry not found: {registry_path}")
    with registry_path.open(encoding="utf-8") as registry_file:
        registry = yaml.safe_load(registry_file)
    if not isinstance(registry, dict) or "sources" not in registry:
        raise CollectionError("source registry must contain a sources mapping")
    return registry


def append_download_log(log_path: Path, entry: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        with log_path.open(encoding="utf-8") as log_file:
            payload = json.load(log_file)
    else:
        payload = {"version": "0.1.0", "status": "initialized", "entries": []}

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise CollectionError(f"download log entries must be a list: {log_path}")

    next_payload = {
        **payload,
        "entries": [
            *entries,
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                **entry,
            },
        ],
    }

    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=log_path.parent,
        encoding="utf-8",
    ) as temp_file:
        json.dump(next_payload, temp_file, indent=2, sort_keys=True)
        temp_file.write("\n")
        temp_name = temp_file.name
    os.replace(temp_name, log_path)


def build_base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and planned outputs without downloading data.")
    parser.add_argument("--source-registry", default=str(DEFAULT_REGISTRY_PATH), help="Path to metadata/source_registry.yaml.")
    parser.add_argument("--download-log", default=str(DEFAULT_DOWNLOAD_LOG_PATH), help="Append-only JSON audit log path.")
    parser.add_argument("--output-dir", help="Override source output directory.")
    parser.add_argument("--start-date", help="UTC start date in YYYY-MM-DD format, when relevant.")
    parser.add_argument("--end-date", help="UTC end date in YYYY-MM-DD format, when relevant.")
    parser.add_argument("--zones-geojson", default="metadata/zones.geojson", help="Zone geometry GeoJSON path.")
    parser.add_argument("--zone-registry", default="metadata/zone_registry.csv", help="Zone registry CSV path.")
    parser.add_argument("--provider", help="Provider selector for adapters with multiple public providers.")
    parser.add_argument("--max-retries", type=int, default=3, help="Retry budget for future real API calls.")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="Timeout for future real API calls.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging verbosity.")
    return parser


def validate_common_args(args: argparse.Namespace) -> None:
    if args.max_retries < 0:
        raise CollectionError("--max-retries must be >= 0")
    if args.timeout_seconds <= 0:
        raise CollectionError("--timeout-seconds must be > 0")
    start_date = parse_iso_date(args.start_date, "--start-date") if args.start_date else None
    end_date = parse_iso_date(args.end_date, "--end-date") if args.end_date else None
    if start_date and end_date and start_date > end_date:
        raise CollectionError("--start-date must be <= --end-date")


def parse_iso_date(value: str, arg_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise CollectionError(f"{arg_name} must use YYYY-MM-DD format") from error


def source_entry(source_id: str, registry: dict[str, Any]) -> dict[str, Any]:
    source = registry["sources"].get(source_id)
    if not isinstance(source, dict):
        raise CollectionError(f"source not found in registry: {source_id}")
    return source


def source_is_enabled(source: dict[str, Any]) -> bool:
    return source.get("enabled", True) is True


def planned_output_dir(args: argparse.Namespace, source: dict[str, Any]) -> Path:
    output_dir = getattr(args, "output_dir", None) or source["output_dir"]
    resolved = safe_writable_path(output_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def selected_provider(args: argparse.Namespace, source: dict[str, Any]) -> dict[str, Any] | None:
    providers = source.get("provider_priority")
    if not providers:
        return None
    if args.provider:
        for provider in providers:
            if provider["id"] == args.provider:
                return provider
        raise CollectionError(f"unknown provider for {source['id']}: {args.provider}")
    return providers[0]


def build_log_entry(
    *,
    source_id: str,
    script_name: str,
    status: str,
    output_dir: Path | None,
    dry_run: bool,
    message: str,
    credential_policy: str | None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "script": script_name,
        "status": status,
        "dry_run": dry_run,
        "writes_primary_data": False,
        "output_dir": str(output_dir) if output_dir else None,
        "credential_policy": credential_policy,
        "message": message,
    }


def run_source_cli(source_id: str, script_name: str) -> int:
    parser = build_base_parser(f"{script_name}: dry-run-ready public data collection scaffold")
    args = parser.parse_args()
    configure_logging(args.log_level)
    logger = logging.getLogger(script_name)

    try:
        validate_common_args(args)
        registry_path = safe_project_path(args.source_registry)
        download_log_path = safe_writable_path(args.download_log)
        registry = load_source_registry(registry_path)
        source = source_entry(source_id, registry)
        output_dir = planned_output_dir(args, source)
        provider = selected_provider(args, source)

        if not source_is_enabled(source):
            status = "DISABLED"
            message = source.get("disabled_reason", "Source is disabled in source registry.")
            append_download_log(
                download_log_path,
                build_log_entry(
                    source_id=source_id,
                    script_name=script_name,
                    status=status,
                    output_dir=output_dir,
                    dry_run=args.dry_run,
                    message=message,
                    credential_policy=source.get("credential_policy"),
                ),
            )
            logger.warning(message)
            print(
                json.dumps(
                    {
                        "source_id": source_id,
                        "script": script_name,
                        "status": status,
                        "reason": message,
                        "output_dir": str(output_dir),
                        "writes_primary_data": False,
                    },
                    sort_keys=True,
                )
            )
            return 0 if args.dry_run else 2

        if args.dry_run:
            message = "Dry-run completed without network, credentials, or primary data writes."
            append_download_log(
                download_log_path,
                build_log_entry(
                    source_id=source_id,
                    script_name=script_name,
                    status="PASS",
                    output_dir=output_dir,
                    dry_run=True,
                    message=message,
                    credential_policy=source.get("credential_policy"),
                ),
            )
            logger.info(message)
            print(
                json.dumps(
                    {
                        "source_id": source_id,
                        "script": script_name,
                        "status": "PASS",
                        "output_dir": str(output_dir),
                        "provider": provider,
                        "writes_primary_data": False,
                    },
                    sort_keys=True,
                )
            )
            return 0

        message = "Real download is disabled until APPROVE DATA REAL DOWNLOAD; credential and API calls require the explicit real-download approval gate."
        append_download_log(
            download_log_path,
            build_log_entry(
                source_id=source_id,
                script_name=script_name,
                status="BLOCKED_AUTH",
                output_dir=output_dir,
                dry_run=False,
                message=message,
                credential_policy=source.get("credential_policy"),
            ),
        )
        logger.error(message)
        return 2
    except (CollectionError, OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as error:
        logger.error("Collection command failed: %s", error)
        return 1


def run_utility_cli(script_name: str) -> int:
    parser = build_base_parser(f"{script_name}: dry-run-ready utility scaffold")
    args, _unknown = parser.parse_known_args()
    configure_logging(args.log_level)
    logger = logging.getLogger(script_name)
    try:
        validate_common_args(args)
        output_dir = safe_writable_path(args.output_dir) if args.output_dir else None
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
        if args.dry_run:
            logger.info("Utility dry-run completed.")
            print(
                json.dumps(
                    {
                        "script": script_name,
                        "status": "PASS",
                        "output_dir": str(output_dir) if output_dir else None,
                        "writes_primary_data": False,
                    },
                    sort_keys=True,
                )
            )
            return 0
        logger.error("Real execution is disabled in Phase 2 for this scaffold utility.")
        return 2
    except (CollectionError, OSError, ValueError) as error:
        logger.error("Utility command failed: %s", error)
        return 1

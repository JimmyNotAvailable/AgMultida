from __future__ import annotations

import argparse
import csv
import json
import logging

from data_collection_common import (
    CollectionError,
    append_download_log,
    build_log_entry,
    configure_logging,
    load_source_registry,
    planned_output_dir,
    safe_project_path,
    safe_writable_path,
    source_is_enabled,
    validate_common_args,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Data collection orchestrator scaffold")
    parser.add_argument("--dry-run", action="store_true", help="Validate planned collection without downloading primary data.")
    parser.add_argument("--source-registry", default="metadata/source_registry.yaml", help="Path to metadata/source_registry.yaml.")
    parser.add_argument("--download-log", default="metadata/download_log.json", help="Append-only JSON audit log path.")
    parser.add_argument("--coverage-report", default="reports/coverage_report.csv", help="CSV report written during dry-run.")
    parser.add_argument("--start-date", help="UTC start date in YYYY-MM-DD format, when relevant.")
    parser.add_argument("--end-date", help="UTC end date in YYYY-MM-DD format, when relevant.")
    parser.add_argument("--max-retries", type=int, default=3, help="Retry budget for future real API calls.")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="Timeout for future real API calls.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging verbosity.")
    args = parser.parse_args()
    configure_logging(args.log_level)
    logger = logging.getLogger("run_data_collection")

    try:
        validate_common_args(args)
        registry = load_source_registry(safe_project_path(args.source_registry))
        download_log_path = safe_writable_path(args.download_log)
        report_path = safe_writable_path(args.coverage_report)

        if not args.dry_run:
            message = "Real collection is disabled until APPROVE DATA REAL DOWNLOAD; run dry-run only until the explicit real-download approval gate."
            append_download_log(
                download_log_path,
                {
                    "source_id": "orchestrator",
                    "script": "run_data_collection",
                    "status": "BLOCKED_AUTH",
                    "dry_run": False,
                    "writes_primary_data": False,
                    "output_dir": None,
                    "credential_policy": "phase_gate_required",
                    "message": message,
                },
            )
            logger.error(message)
            return 2

        rows = []
        for source_id, source in registry["sources"].items():
            output_dir = planned_output_dir(args, source)
            if not source_is_enabled(source):
                status = "DISABLED"
                message = source.get("disabled_reason", "Source disabled in source registry.")
            elif source.get("auth_required") and not source.get("required"):
                status = "OPTIONAL_BLOCKED"
                message = "Optional auth-gated source is not required for the GEE-free minimum path."
            else:
                status = "PASS"
                message = "Dry-run collection plan validated without network or credential use."
            append_download_log(
                download_log_path,
                build_log_entry(
                    source_id=source_id,
                    script_name=source["script"],
                    status=status,
                    output_dir=output_dir,
                    dry_run=True,
                    message=message,
                    credential_policy=source.get("credential_policy"),
                ),
            )
            rows.append(
                {
                    "source_id": source_id,
                    "status": status,
                    "priority": source.get("priority"),
                    "output_dir": str(output_dir),
                    "writes_primary_data": False,
                }
            )

        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", newline="", encoding="utf-8") as report_file:
            writer = csv.DictWriter(
                report_file,
                fieldnames=["source_id", "status", "priority", "output_dir", "writes_primary_data"],
            )
            writer.writeheader()
            writer.writerows(rows)

        logger.info("Dry-run collection plan validated for %s sources.", len(rows))
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "sources_checked": len(rows),
                    "required_ready_sources": [
                        row["source_id"]
                        for row in rows
                        if row["status"] == "PASS"
                        and registry["sources"][row["source_id"]].get("required") is True
                    ],
                    "coverage_report": str(report_path),
                    "writes_primary_data": False,
                },
                sort_keys=True,
            )
        )
        return 0
    except (CollectionError, OSError, ValueError, json.JSONDecodeError) as error:
        logger.error("Data collection orchestration failed: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

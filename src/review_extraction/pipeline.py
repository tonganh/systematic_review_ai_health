from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .config import PipelineConfig
from .io_utils import ensure_output_dir, list_pdf_files, reset_dir, safe_stem, utc_now_iso, write_json
from .openai_client import OpenAIPdfExtractionClient
from .schema import flatten_primary_studies, normalize_review_record, parse_json_object


def run_pipeline(config: PipelineConfig) -> dict[str, Any]:
    ensure_output_dir(config.output_dir)
    reset_dir(config.per_file_dir)

    client = OpenAIPdfExtractionClient(model=config.model)
    pdf_files = list_pdf_files(config.papers_dir)
    extraction_records: list[dict[str, Any]] = []
    primary_studies_records: list[dict[str, Any]] = []

    report: dict[str, Any] = {
        "started_at": utc_now_iso(),
        "finished_at": "",
        "model": config.model,
        "papers_dir": str(config.papers_dir),
        "output_dir": str(config.output_dir),
        "total_files_found": len(pdf_files),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "per_file_summaries_written": 0,
        "primary_studies_rows_written": 0,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "errors": [],
    }

    for pdf_path in pdf_files:
        report["processed"] += 1
        extraction = client.extract(pdf_path)
        _merge_usage(report["usage"], extraction.usage)

        parsed, parse_error = parse_json_object(extraction.output_text)
        normalized = None
        issues: list[str] = []

        if parse_error:
            issues.append(parse_error)
        else:
            normalized, validation_issues = normalize_review_record(parsed, source_file=pdf_path.name)
            issues.extend(validation_issues)

        attempt_count = 0
        while issues and attempt_count < config.max_retries:
            attempt_count += 1
            repaired = client.repair(pdf_path, extraction.output_text, issues)
            _merge_usage(report["usage"], repaired.usage)
            extraction = repaired
            parsed, parse_error = parse_json_object(extraction.output_text)
            normalized = None
            issues = []
            if parse_error:
                issues.append(parse_error)
            else:
                normalized, validation_issues = normalize_review_record(parsed, source_file=pdf_path.name)
                issues.extend(validation_issues)

        if normalized is None or issues:
            report["failed"] += 1
            report["errors"].append(
                {
                    "source_file": pdf_path.name,
                    "issues": issues if issues else ["failed to produce normalized record"],
                    "response_id": extraction.response_id,
                }
            )
            continue

        extraction_records.append(normalized)
        primary_rows = flatten_primary_studies(normalized)
        primary_studies_records.extend(primary_rows)
        per_file_path = config.per_file_dir / f"{safe_stem(pdf_path.name)}.json"
        write_json(per_file_path, normalized)
        report["per_file_summaries_written"] += 1
        report["primary_studies_rows_written"] += len(primary_rows)
        report["success"] += 1

    write_json(config.extractions_path, extraction_records)
    write_json(config.primary_studies_path, primary_studies_records)
    report["finished_at"] = utc_now_iso()
    write_json(config.run_report_path, report)
    return report


def _merge_usage(target: dict[str, int], usage: dict[str, int]) -> None:
    target["input_tokens"] += usage.get("input_tokens", 0)
    target["output_tokens"] += usage.get("output_tokens", 0)
    target["total_tokens"] += usage.get("total_tokens", 0)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract review fields from PDF papers via OpenAI.")
    parser.add_argument("--papers-dir", default="papers")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--model", default="gpt-5")
    parser.add_argument("--max-retries", type=int, default=1)
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = PipelineConfig(
        papers_dir=Path(args.papers_dir),
        output_dir=Path(args.output_dir),
        model=args.model,
        max_retries=max(0, args.max_retries),
    )
    report = run_pipeline(config)
    print(
        "processed={processed} success={success} failed={failed} primary_rows={primary}".format(
            processed=report["processed"],
            success=report["success"],
            failed=report["failed"],
            primary=report["primary_studies_rows_written"],
        )
    )


if __name__ == "__main__":
    main()


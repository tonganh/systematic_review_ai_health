from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook

PAPER_COLUMNS = [
    "source_file",
    "title",
    "year",
    "type_of_paper",
    "population",
    "ai_type_application",
    "mental_health_outcome",
    "positive_effects",
    "negative_effects",
    "evidence_type",
    "main_finding",
    "limitations_bias",
    "relevance_to_our_review",
    "use_decision",
    "notes_for_research_question",
    "is_review_paper",
    "primary_studies_count",
]

PRIMARY_COLUMNS = [
    "source_file",
    "review_title",
    "review_year",
    "use_decision",
    "study_title",
    "year",
    "authors",
    "doi_or_identifier",
    "why_relevant",
]


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _normalize_cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _write_sheet(workbook: Workbook, name: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    sheet = workbook.create_sheet(title=name)
    sheet.append(columns)
    for row in rows:
        sheet.append([_normalize_cell(row.get(col, "")) for col in columns])


def export_to_excel(
    extractions_json: Path,
    primary_studies_json: Path,
    output_excel: Path,
) -> Path:
    paper_rows = _load_json_array(extractions_json)
    primary_rows = _load_json_array(primary_studies_json)

    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    _write_sheet(workbook, "papers_answers", paper_rows, PAPER_COLUMNS)
    _write_sheet(workbook, "primary_studies", primary_rows, PRIMARY_COLUMNS)

    output_excel.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_excel)
    return output_excel


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export extraction JSON files to Excel.")
    parser.add_argument("--extractions-json", default="outputs/extractions.json")
    parser.add_argument("--primary-json", default="outputs/primary_studies.json")
    parser.add_argument("--output-excel", default="outputs/review_summary.xlsx")
    return parser


def main() -> None:
    args = _parser().parse_args()
    output_path = export_to_excel(
        extractions_json=Path(args.extractions_json),
        primary_studies_json=Path(args.primary_json),
        output_excel=Path(args.output_excel),
    )
    print(f"excel_exported={output_path}")


if __name__ == "__main__":
    main()


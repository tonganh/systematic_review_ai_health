from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from review_extraction.schema import flatten_primary_studies, normalize_review_record


def main() -> None:
    extractions_path = ROOT / "outputs" / "extractions.json"
    primary_path = ROOT / "outputs" / "primary_studies.json"
    data = json.loads(extractions_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("extractions.json must be a JSON array")
    merged = []
    all_issues = []
    for rec in data:
        if not isinstance(rec, dict):
            continue
        src = str(rec.get("source_file", ""))
        norm, issues = normalize_review_record(rec, source_file=src)
        merged.append(norm)
        if issues:
            all_issues.append({"source_file": src, "issues": issues})
    extractions_path.write_text(json.dumps(merged, ensure_ascii=True, indent=2), encoding="utf-8")
    primary = []
    for rec in merged:
        primary.extend(flatten_primary_studies(rec))
    primary_path.write_text(json.dumps(primary, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"records={len(merged)} primary_rows={len(primary)} notes={len(all_issues)}")


if __name__ == "__main__":
    main()

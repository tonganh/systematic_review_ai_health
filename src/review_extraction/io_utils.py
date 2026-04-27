from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_pdf_files(papers_dir: Path) -> list[Path]:
    if not papers_dir.exists():
        return []
    return sorted(path for path in papers_dir.glob("*.pdf") if path.is_file())


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def reset_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for item in path.glob("*.json"):
        if item.is_file():
            item.unlink()


def safe_stem(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return stem or "paper"


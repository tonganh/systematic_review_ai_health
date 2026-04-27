from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PipelineConfig:
    papers_dir: Path
    output_dir: Path
    model: str
    max_retries: int = 1

    @property
    def extractions_path(self) -> Path:
        return self.output_dir / "extractions.json"

    @property
    def primary_studies_path(self) -> Path:
        return self.output_dir / "primary_studies.json"

    @property
    def per_file_dir(self) -> Path:
        return self.output_dir / "per_file"

    @property
    def run_report_path(self) -> Path:
        return self.output_dir / "run_report.json"


from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

ALLOWED_USE_DECISIONS = {"Include", "Maybe", "Exclude"}

PRIMARY_STUDY_TEMPLATE: dict[str, Any] = {
    "study_title": "",
    "year": "",
    "authors": "",
    "doi_or_identifier": "",
    "why_relevant": "",
}

REVIEW_RECORD_TEMPLATE: dict[str, Any] = {
    "title": "",
    "year": "",
    "type_of_paper": "",
    "population": "",
    "ai_type_application": "",
    "mental_health_outcome": "",
    "positive_effects": "",
    "negative_effects": "",
    "evidence_type": "",
    "main_finding": "",
    "limitations_bias": "",
    "relevance_to_our_review": "",
    "use_decision": "Maybe",
    "notes_for_research_question": "",
    "is_review_paper": True,
    "primary_studies": [],
    "primary_studies_count": 0,
    "source_file": "",
}


def schema_for_prompt() -> dict[str, Any]:
    return deepcopy(REVIEW_RECORD_TEMPLATE)


def build_extraction_prompt() -> str:
    schema_json = json.dumps(schema_for_prompt(), ensure_ascii=True, indent=2)
    return (
        "Extract evidence from this paper for a systematic review about AI effects on mental health. "
        "Return JSON only. Do not include markdown fences or extra text. "
        "Fill all keys from this exact schema. "
        "If data is missing, use empty string. "
        "For primary_studies, list cited studies that are likely primary research papers, with as much citation detail as available. "
        "Only include a primary_studies item if study_title is a real non-empty paper title. "
        "Do not output placeholder items. "
        "If no valid primary study can be identified, return primary_studies as an empty list.\n\n"
        f"{schema_json}"
    )


def build_repair_prompt(previous_output: str, issues: list[str]) -> str:
    issues_text = "; ".join(issues) if issues else "Invalid JSON shape"
    schema_json = json.dumps(schema_for_prompt(), ensure_ascii=True, indent=2)
    return (
        "Your previous output was invalid. Return JSON only and fix all issues.\n"
        f"Issues: {issues_text}\n"
        "Use this exact schema and keep every key present.\n"
        f"{schema_json}\n"
        "Previous output:\n"
        f"{previous_output}"
    )


def parse_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or start >= end:
            return None, "response is not valid JSON"
        fragment = cleaned[start : end + 1]
        try:
            obj = json.loads(fragment)
        except json.JSONDecodeError as exc:
            return None, f"response JSON parsing failed: {exc}"
    if not isinstance(obj, dict):
        return None, "response JSON root must be an object"
    return obj, None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def normalize_primary_study(entry: Any) -> dict[str, Any]:
    normalized = deepcopy(PRIMARY_STUDY_TEMPLATE)
    if not isinstance(entry, dict):
        return normalized
    for key in PRIMARY_STUDY_TEMPLATE:
        normalized[key] = _normalize_text(entry.get(key, ""))
    return normalized


def _is_empty_primary_study(entry: dict[str, Any]) -> bool:
    return all(not _normalize_text(entry.get(key, "")) for key in PRIMARY_STUDY_TEMPLATE)


def _is_valid_primary_study(entry: dict[str, Any]) -> bool:
    title = _normalize_text(entry.get("study_title", ""))
    doi = _normalize_text(entry.get("doi_or_identifier", ""))
    has_alpha_title = any(ch.isalpha() for ch in title)
    if has_alpha_title and len(title) >= 8:
        return True
    if doi:
        return True
    return False


def normalize_review_record(
    record: dict[str, Any],
    source_file: str,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    normalized = deepcopy(REVIEW_RECORD_TEMPLATE)

    for key in REVIEW_RECORD_TEMPLATE:
        if key in {"primary_studies", "primary_studies_count", "is_review_paper", "source_file"}:
            continue
        normalized[key] = _normalize_text(record.get(key, ""))

    use_decision = normalized["use_decision"]
    if use_decision not in ALLOWED_USE_DECISIONS:
        errors.append("use_decision must be Include, Maybe, or Exclude")
        normalized["use_decision"] = "Maybe"

    is_review_paper = record.get("is_review_paper", True)
    normalized["is_review_paper"] = bool(is_review_paper)

    primary_studies_raw = record.get("primary_studies", [])
    if not isinstance(primary_studies_raw, list):
        errors.append("primary_studies must be a list")
        primary_studies_raw = []

    primary_studies = []
    dropped_invalid_count = 0
    for item in primary_studies_raw:
        normalized_item = normalize_primary_study(item)
        if _is_empty_primary_study(normalized_item):
            continue
        if _is_valid_primary_study(normalized_item):
            primary_studies.append(normalized_item)
        else:
            dropped_invalid_count += 1

    if not normalized["is_review_paper"]:
        primary_studies = []
    elif dropped_invalid_count > 0:
        errors.append("primary_studies entries must include a non-empty study_title or doi_or_identifier")

    normalized["primary_studies"] = primary_studies
    normalized["primary_studies_count"] = len(primary_studies)
    normalized["source_file"] = source_file
    year_value = normalized["year"]
    if year_value and not year_value.isdigit():
        errors.append("year should be numeric when provided")

    return normalized, errors


def flatten_primary_studies(record: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    primary = record.get("primary_studies", [])
    if not isinstance(primary, list):
        return rows
    for item in primary:
        normalized_item = normalize_primary_study(item)
        rows.append(
            {
                "source_file": record.get("source_file", ""),
                "review_title": record.get("title", ""),
                "review_year": record.get("year", ""),
                "use_decision": record.get("use_decision", ""),
                **normalized_item,
            }
        )
    return rows


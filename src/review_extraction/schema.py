from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

ALLOWED_USE_DECISIONS = {"Include", "Maybe", "Exclude"}
ALLOWED_ADVERSE_EVENTS = {"Yes", "No", "Not clear"}
ALLOWED_CLAIMS_CAUSALITY = {"Yes", "No", "Partial"}
ALLOWED_EVIDENCE_CAUSALITY = {"Strong", "Moderate", "Weak", "Not applicable"}
NOT_REPORTED_DOI = "Not reported in source review"

PRIMARY_STUDY_TEMPLATE: dict[str, Any] = {
    "study_title": "",
    "year": "",
    "authors": "",
    "doi_or_identifier": "",
    "why_relevant": "",
}

CONTROLLED_CONFOUNDERS_TEMPLATE: dict[str, Any] = {
    "baseline_mental_health_condition": "",
    "medical_condition": "",
    "family_social_factors": "",
    "addiction_problematic_use": "",
    "demographics": "",
    "other_confounders": "",
}

REVIEW_RECORD_TEMPLATE: dict[str, Any] = {
    "title": "",
    "year": "",
    "journal_or_conference": "",
    "type_of_paper": "",
    "study_design": "",
    "population": "",
    "sample_size": "",
    "country_or_setting": "",
    "ai_type_application": "",
    "ai_exposure_intervention": "",
    "comparator_control_group": "",
    "mental_health_outcome": "",
    "outcome_measurement_tool": "",
    "positive_effects": "",
    "negative_effects_harms": "",
    "adverse_events_reported": "",
    "evidence_type": "",
    "main_finding": "",
    "effect_size_key_result": "",
    "study_claims_causality": "",
    "evidence_supports_causality": "",
    "controlled_confounders": deepcopy(CONTROLLED_CONFOUNDERS_TEMPLATE),
    "limitations_bias": "",
    "relevance_to_our_review": "",
    "use_decision": "Maybe",
    "reason_for_decision": "",
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
        "Extract information from this paper for a systematic review about AI effects on mental health. "
        "Return JSON only. Do not include markdown fences or extra text. "
        "Fill all keys from this exact schema. Use empty string for unknown text fields. "
        "For adverse_events_reported use exactly one of: Yes, No, Not clear. "
        "For study_claims_causality use exactly one of: Yes, No, Partial. "
        "For evidence_supports_causality use exactly one of: Strong, Moderate, Weak, Not applicable. "
        "For use_decision use exactly one of: Include, Maybe, Exclude. "
        "Fill controlled_confounders sub-keys with what the study adjusted for or controlled; use empty string if not reported. "
        "For primary_studies (only when is_review_paper is true), list cited primary research with study_title, year, authors, doi_or_identifier, why_relevant. "
        "Only include a primary_studies item if study_title is a real non-empty title. "
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


def _canonical_enum(value: str, allowed: set[str]) -> str:
    if not value:
        return ""
    for option in allowed:
        if value.strip().lower() == option.lower():
            return option
    return value


def normalize_primary_study(entry: Any) -> dict[str, Any]:
    normalized = deepcopy(PRIMARY_STUDY_TEMPLATE)
    if not isinstance(entry, dict):
        return normalized
    for key in PRIMARY_STUDY_TEMPLATE:
        normalized[key] = _normalize_text(entry.get(key, ""))
    if not normalized["doi_or_identifier"]:
        normalized["doi_or_identifier"] = NOT_REPORTED_DOI
    if not normalized["why_relevant"]:
        normalized["why_relevant"] = "Cited as primary evidence in the source review"
    return normalized


def _is_empty_primary_study(entry: dict[str, Any]) -> bool:
    return all(not _normalize_text(entry.get(key, "")) for key in PRIMARY_STUDY_TEMPLATE)


def _is_valid_primary_study(entry: dict[str, Any]) -> bool:
    title = _normalize_text(entry.get("study_title", ""))
    doi = _normalize_text(entry.get("doi_or_identifier", ""))
    has_alpha_title = any(ch.isalpha() for ch in title)
    if has_alpha_title and len(title) >= 8:
        return True
    if doi and doi != NOT_REPORTED_DOI:
        return True
    return False


def normalize_review_record(
    record: dict[str, Any],
    source_file: str,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    normalized = deepcopy(REVIEW_RECORD_TEMPLATE)

    skip_keys = {
        "primary_studies",
        "primary_studies_count",
        "is_review_paper",
        "source_file",
        "controlled_confounders",
    }

    for key in REVIEW_RECORD_TEMPLATE:
        if key in skip_keys:
            continue
        normalized[key] = _normalize_text(record.get(key, ""))

    if not normalized["negative_effects_harms"]:
        normalized["negative_effects_harms"] = _normalize_text(
            record.get("negative_effects_harms", record.get("negative_effects", ""))
        )

    if not normalized["reason_for_decision"]:
        normalized["reason_for_decision"] = _normalize_text(record.get("reason_for_decision", ""))

    cc_raw = record.get("controlled_confounders", {})
    normalized_cc = deepcopy(CONTROLLED_CONFOUNDERS_TEMPLATE)
    if isinstance(cc_raw, dict):
        for key in CONTROLLED_CONFOUNDERS_TEMPLATE:
            normalized_cc[key] = _normalize_text(cc_raw.get(key, ""))
    normalized["controlled_confounders"] = normalized_cc

    normalized["adverse_events_reported"] = _canonical_enum(
        normalized["adverse_events_reported"], ALLOWED_ADVERSE_EVENTS
    )
    if normalized["adverse_events_reported"] and normalized["adverse_events_reported"] not in ALLOWED_ADVERSE_EVENTS:
        errors.append("adverse_events_reported must be Yes, No, or Not clear")

    normalized["study_claims_causality"] = _canonical_enum(
        normalized["study_claims_causality"], ALLOWED_CLAIMS_CAUSALITY
    )
    if (
        normalized["study_claims_causality"]
        and normalized["study_claims_causality"] not in ALLOWED_CLAIMS_CAUSALITY
    ):
        errors.append("study_claims_causality must be Yes, No, or Partial")

    normalized["evidence_supports_causality"] = _canonical_enum(
        normalized["evidence_supports_causality"], ALLOWED_EVIDENCE_CAUSALITY
    )
    if (
        normalized["evidence_supports_causality"]
        and normalized["evidence_supports_causality"] not in ALLOWED_EVIDENCE_CAUSALITY
    ):
        errors.append("evidence_supports_causality must be Strong, Moderate, Weak, or Not applicable")

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
    if year_value and not re.fullmatch(r"\d{4}", year_value):
        errors.append("year should be a four-digit year when provided")

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


def paper_record_for_export(record: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    base = deepcopy(REVIEW_RECORD_TEMPLATE)
    for key in base:
        if key == "controlled_confounders":
            continue
        if key in {"primary_studies"}:
            continue
        row[key] = record.get(key, "")
    if not row.get("negative_effects_harms") and record.get("negative_effects"):
        row["negative_effects_harms"] = _normalize_text(record.get("negative_effects"))
    cc_in = record.get("controlled_confounders")
    cc_out = deepcopy(CONTROLLED_CONFOUNDERS_TEMPLATE)
    if isinstance(cc_in, dict):
        for key in CONTROLLED_CONFOUNDERS_TEMPLATE:
            cc_out[key] = _normalize_text(cc_in.get(key, ""))
    for key, val in cc_out.items():
        row[f"confounder_{key}"] = val
    row["primary_studies_count"] = record.get("primary_studies_count", len(record.get("primary_studies") or []))
    row["is_review_paper"] = record.get("is_review_paper", "")
    row["source_file"] = record.get("source_file", "")
    return row

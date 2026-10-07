"""Validation for the test-case JSON document produced by the skill.

The formal contract lives in ../references/test-case-schema.json; this module
enforces it (plus quality rules a JSON Schema cannot express) without needing
the third-party `jsonschema` package.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

TEST_TYPES = {
    "Functional",
    "Negative",
    "Boundary",
    "UI",
    "Integration",
    "Security",
    "Accessibility",
    "Usability",
    "Performance",
    "Compatibility",
    "Data Integrity",
    "Regression",
}

TECHNIQUES = {
    "Equivalence Partitioning",
    "Boundary Value Analysis",
    "Decision Table",
    "State Transition",
    "Use Case / Scenario",
    "Error Guessing",
    "Pairwise",
    "Checklist",
    "Exploratory Charter",
}

TC_ID_PATTERN = re.compile(r"^TC-\d+-\d{3}$")
REQ_ID_PATTERN = re.compile(r"^(AC|REQ|NFR|IMP)-\d+$")

# Phrases that make an expected result unverifiable.
VAGUE_EXPECTATIONS = re.compile(
    r"\b(works?( fine| properly| correctly)?|as expected|correctly|properly|should be (fine|ok)|is ok|no issues?)\b\.?$",
    re.IGNORECASE,
)
MAX_TITLE_LENGTH = 128
MAX_STEPS_WARNING = 15


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from None


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate(doc: Any) -> ValidationReport:
    report = ValidationReport()
    err, warn = report.errors.append, report.warnings.append

    if not isinstance(doc, dict):
        err("Top level must be a JSON object.")
        return report

    if doc.get("schema_version") != SCHEMA_VERSION:
        err(f"schema_version must be '{SCHEMA_VERSION}'.")

    story = doc.get("story")
    story_id = None
    if not isinstance(story, dict) or not isinstance(story.get("id"), int) or not _non_empty_str(story.get("title")):
        err("story must be an object with integer 'id' and non-empty 'title'.")
    else:
        story_id = story["id"]

    for key in ("assumptions", "open_questions", "out_of_scope"):
        value = doc.get(key, [])
        if not isinstance(value, list) or not all(_non_empty_str(v) for v in value):
            err(f"'{key}' must be a list of non-empty strings.")

    requirements = doc.get("requirements")
    requirement_ids: dict[str, dict] = {}
    if not isinstance(requirements, list) or not requirements:
        err("requirements must be a non-empty list.")
        requirements = []
    for index, req in enumerate(requirements):
        where = f"requirements[{index}]"
        if not isinstance(req, dict):
            err(f"{where} must be an object.")
            continue
        req_id = req.get("id")
        if not isinstance(req_id, str) or not REQ_ID_PATTERN.match(req_id):
            err(f"{where}.id '{req_id}' must look like AC-1, REQ-1, NFR-1 or IMP-1.")
            continue
        if req_id in requirement_ids:
            err(f"Duplicate requirement id {req_id}.")
        if not _non_empty_str(req.get("text")):
            err(f"{where} ({req_id}) needs non-empty 'text'.")
        if req.get("source") not in {"acceptance_criteria", "description", "parent", "comment", "implicit", "user"}:
            err(f"{where} ({req_id}).source must be one of acceptance_criteria, description, parent, comment, implicit, user.")
        requirement_ids[req_id] = req

    test_cases = doc.get("test_cases")
    if not isinstance(test_cases, list) or not test_cases:
        err("test_cases must be a non-empty list.")
        return report

    seen_ids: set[str] = set()
    seen_titles: dict[str, str] = {}
    covered: set[str] = set()
    for index, tc in enumerate(test_cases):
        where = f"test_cases[{index}]"
        if not isinstance(tc, dict):
            err(f"{where} must be an object.")
            continue
        tc_id = tc.get("id")
        if not isinstance(tc_id, str) or not TC_ID_PATTERN.match(tc_id):
            err(f"{where}.id '{tc_id}' must match TC-<storyId>-NNN (e.g. TC-{story_id or 1234}-001).")
        else:
            where = tc_id
            if story_id is not None and not tc_id.startswith(f"TC-{story_id}-"):
                err(f"{tc_id}: id prefix does not match story id {story_id}.")
            if tc_id in seen_ids:
                err(f"Duplicate test case id {tc_id}.")
            seen_ids.add(tc_id)

        title = tc.get("title")
        if not _non_empty_str(title):
            err(f"{where}: title is required.")
        else:
            if len(title) > MAX_TITLE_LENGTH:
                warn(f"{where}: title is {len(title)} chars; keep it under {MAX_TITLE_LENGTH}.")
            key = title.strip().lower()
            if key in seen_titles:
                err(f"{where}: duplicate title (same as {seen_titles[key]}).")
            seen_titles[key] = str(tc_id)

        if not _non_empty_str(tc.get("objective")):
            err(f"{where}: objective is required.")
        if tc.get("type") not in TEST_TYPES:
            err(f"{where}: type must be one of {sorted(TEST_TYPES)}.")
        if tc.get("technique") not in TECHNIQUES:
            err(f"{where}: technique must be one of {sorted(TECHNIQUES)}.")
        if tc.get("priority") not in (1, 2, 3, 4):
            err(f"{where}: priority must be an integer 1-4 (1 = highest).")

        refs = tc.get("requirement_refs")
        if not isinstance(refs, list) or not refs:
            err(f"{where}: requirement_refs must list at least one requirement id.")
        else:
            for ref in refs:
                if ref not in requirement_ids:
                    err(f"{where}: requirement_refs contains unknown id '{ref}'.")
                covered.add(ref)

        for list_key in ("preconditions", "postconditions", "tags"):
            value = tc.get(list_key, [])
            if not isinstance(value, list) or not all(_non_empty_str(v) for v in value):
                err(f"{where}: {list_key} must be a list of non-empty strings.")

        test_data = tc.get("test_data", [])
        if not isinstance(test_data, list) or not all(
            isinstance(d, dict) and _non_empty_str(d.get("name")) and "value" in d for d in test_data
        ):
            err(f"{where}: test_data must be a list of {{name, value}} objects.")

        steps = tc.get("steps")
        if not isinstance(steps, list) or not steps:
            err(f"{where}: at least one step is required.")
            continue
        if len(steps) > MAX_STEPS_WARNING:
            warn(f"{where}: {len(steps)} steps; consider splitting into smaller test cases.")
        for step_no, step in enumerate(steps, start=1):
            if not isinstance(step, dict) or not _non_empty_str(step.get("action")):
                err(f"{where} step {step_no}: action is required.")
                continue
            expected = step.get("expected", "")
            if not isinstance(expected, str):
                err(f"{where} step {step_no}: expected must be a string.")
            elif expected and VAGUE_EXPECTATIONS.search(expected.strip()):
                warn(f"{where} step {step_no}: expected result '{expected}' is vague; state the observable outcome.")
        last_expected = steps[-1].get("expected") if isinstance(steps[-1], dict) else None
        if not _non_empty_str(last_expected):
            err(f"{where}: the final step must have an expected result.")

    for req_id, req in requirement_ids.items():
        if req_id not in covered and req.get("testable", True):
            err(f"{req_id} is not covered by any test case (mark it \"testable\": false with a reason if intentional).")
        if req.get("testable") is False and not _non_empty_str(req.get("note")):
            err(f"{req_id} is marked untestable but has no 'note' explaining why.")

    return report


def coverage_matrix(doc: dict) -> dict[str, list[str]]:
    matrix: dict[str, list[str]] = {req["id"]: [] for req in doc.get("requirements", [])}
    for tc in doc.get("test_cases", []):
        for ref in tc.get("requirement_refs", []):
            matrix.setdefault(ref, []).append(tc["id"])
    return matrix

#!/usr/bin/env python3
"""Validate a test-case JSON document and export it for humans and tools.

Outputs (written next to the input unless --out-dir is given):
    <story>-test-cases.md      Reviewable test specification with traceability
    <story>-ado-import.csv     Azure Test Plans CSV import format

Usage:
    python3 export_test_cases.py test-cases/12345/test-cases.json
    python3 export_test_cases.py test-cases/12345/test-cases.json --validate-only
    python3 export_test_cases.py test-cases/12345/test-cases.json --area-path "Proj\\Team" --assigned-to "qa@contoso.com"

Exit codes: 0 valid and exported, 1 validation errors, 2 usage error.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional

from testcase_schema import coverage_matrix, load, validate

PRIORITY_LABELS = {1: "P1 - Critical", 2: "P2 - High", 3: "P3 - Medium", 4: "P4 - Low"}

# Column names expected by Azure Test Plans "Import test cases" (CSV).
ADO_CSV_COLUMNS = [
    "ID",
    "Work Item Type",
    "Title",
    "Test Step",
    "Step Action",
    "Step Expected",
    "Area Path",
    "Assigned To",
    "State",
    "Priority",
    "Tags",
]


def _plain(text: str) -> str:
    """ADO CSV import stores plain text, so drop Markdown bold markers."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", str(text))


def _md_escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")


def render_markdown(doc: dict) -> str:
    story = doc["story"]
    cases = doc["test_cases"]
    matrix = coverage_matrix(doc)
    by_type = Counter(tc["type"] for tc in cases)
    by_priority = Counter(tc["priority"] for tc in cases)
    requirements = {req["id"]: req for req in doc["requirements"]}

    out: list[str] = [
        f"# Test Specification — Story {story['id']}: {story['title']}",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Story | [{story['id']}]({story.get('url', '')}) |" if story.get("url") else f"| Story | {story['id']} |",
        f"| Generated | {doc.get('generated_on', date.today().isoformat())} |",
        f"| Author | {doc.get('author', 'QA')} |",
        f"| Status | {doc.get('status', 'Draft — pending review')} |",
        f"| Total test cases | {len(cases)} |",
        f"| By priority | {', '.join(f'{PRIORITY_LABELS[p]}: {n}' for p, n in sorted(by_priority.items()))} |",
        f"| By type | {', '.join(f'{t}: {n}' for t, n in sorted(by_type.items()))} |",
        "",
    ]

    if doc.get("scope_summary"):
        out += ["## Scope", "", doc["scope_summary"], ""]
    if doc.get("out_of_scope"):
        out += ["## Out of scope", ""] + [f"- {item}" for item in doc["out_of_scope"]] + [""]

    out += ["## Requirements traceability matrix", "", "| Req ID | Source | Requirement | Test cases | Status |", "|---|---|---|---|---|"]
    for req_id, tc_ids in matrix.items():
        req = requirements.get(req_id, {})
        if req.get("testable") is False:
            status = f"Not testable — {req.get('note', '')}"
        else:
            status = "Covered" if tc_ids else "**NOT COVERED**"
        out.append(
            f"| {req_id} | {req.get('source', '')} | {_md_escape(req.get('text', ''))} | {', '.join(tc_ids) or '—'} | {_md_escape(status)} |"
        )
    out.append("")

    if doc.get("assumptions"):
        out += ["## Assumptions", ""] + [f"- {a}" for a in doc["assumptions"]] + [""]
    if doc.get("open_questions"):
        out += ["## Open questions (for PO / Dev)", ""] + [f"{i}. {q}" for i, q in enumerate(doc["open_questions"], 1)] + [""]

    out += ["## Test case index", "", "| ID | Title | Type | Priority | Technique | Covers |", "|---|---|---|---|---|---|"]
    for tc in cases:
        out.append(
            f"| [{tc['id']}](#{tc['id'].lower()}) | {_md_escape(tc['title'])} | {tc['type']} | P{tc['priority']} | {tc['technique']} | {', '.join(tc['requirement_refs'])} |"
        )
    out.append("")

    out += ["## Test cases", ""]
    for tc in cases:
        out += [
            f"### {tc['id']}",
            "",
            f"**{tc['title']}**",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Objective | {_md_escape(tc['objective'])} |",
            f"| Type | {tc['type']} |",
            f"| Priority | {PRIORITY_LABELS[tc['priority']]} |",
            f"| Design technique | {tc['technique']} |",
            f"| Requirements | {', '.join(tc['requirement_refs'])} |",
            f"| Tags | {', '.join(tc.get('tags', [])) or '—'} |",
            "",
        ]
        if tc.get("preconditions"):
            out += ["**Preconditions**", ""] + [f"- {p}" for p in tc["preconditions"]] + [""]
        if tc.get("test_data"):
            out += ["**Test data**", "", "| Name | Value |", "|---|---|"]
            out += [f"| {_md_escape(d['name'])} | `{_md_escape(d['value'])}` |" for d in tc["test_data"]]
            out.append("")
        out += ["**Steps**", "", "| # | Action | Expected result |", "|---|---|---|"]
        out += [
            f"| {n} | {_md_escape(step['action'])} | {_md_escape(step.get('expected', '')) or '—'} |"
            for n, step in enumerate(tc["steps"], 1)
        ]
        out.append("")
        if tc.get("postconditions"):
            out += ["**Postconditions**", ""] + [f"- {p}" for p in tc["postconditions"]] + [""]
    return "\n".join(out).rstrip() + "\n"


def write_ado_csv(doc: dict, path: Path, area_path: str, assigned_to: str, state: str) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(ADO_CSV_COLUMNS)
        for tc in doc["test_cases"]:
            title = f"{tc['id']}: {tc['title']}"
            tags = "; ".join([f"Story-{doc['story']['id']}", tc["type"], *tc.get("tags", [])])
            steps = list(tc["steps"])
            # CSV import has no Description column, so preconditions and test
            # data become an initial setup step that the tester confirms.
            setup = [*tc.get("preconditions", [])]
            setup += [f"Test data — {d['name']}: {d['value']}" for d in tc.get("test_data", [])]
            if setup:
                steps.insert(0, {"action": "Setup:\n" + "\n".join(f"- {s}" for s in setup), "expected": "All preconditions are met."})
            first = steps[0]
            writer.writerow(
                ["", "Test Case", _plain(title), "1", _plain(first["action"]), _plain(first.get("expected", "")), area_path, assigned_to, state, tc["priority"], tags]
            )
            for number, step in enumerate(steps[1:], start=2):
                writer.writerow(["", "", "", str(number), _plain(step["action"]), _plain(step.get("expected", "")), "", "", "", "", ""])


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="Path to the test-case JSON document")
    parser.add_argument("--out-dir", type=Path, help="Output directory (default: alongside the input)")
    parser.add_argument("--validate-only", action="store_true", help="Validate and report coverage; write nothing")
    parser.add_argument("--area-path", default="", help="Area Path for the CSV (blank = ADO default)")
    parser.add_argument("--assigned-to", default="", help="Assigned To for the CSV")
    parser.add_argument("--state", default="Design", help="Initial test case state for the CSV (default: Design)")
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(f"ERROR: {args.input} does not exist.", file=sys.stderr)
        return 2
    try:
        doc = load(args.input)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    report = validate(doc)
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    if not report.ok:
        print(f"\nValidation failed with {len(report.errors)} error(s). Nothing exported.")
        return 1

    matrix = coverage_matrix(doc)
    covered = sum(1 for ids in matrix.values() if ids)
    print(f"Valid: {len(doc['test_cases'])} test cases, {covered}/{len(matrix)} requirements covered, {len(report.warnings)} warning(s).")
    if args.validate_only:
        return 0

    out_dir = args.out_dir or args.input.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    story_id = doc["story"]["id"]
    md_path = out_dir / f"{story_id}-test-cases.md"
    csv_path = out_dir / f"{story_id}-ado-import.csv"
    md_path.write_text(render_markdown(doc), encoding="utf-8")
    write_ado_csv(doc, csv_path, args.area_path, args.assigned_to, args.state)
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

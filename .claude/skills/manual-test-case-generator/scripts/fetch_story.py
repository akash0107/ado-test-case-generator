#!/usr/bin/env python3
"""Fetch an Azure DevOps work item (user story, PBI, bug, ...) with everything
needed for test design: description, acceptance criteria, parent/child/related
items, existing linked test cases, attachments and discussion comments.

Usage:
    python3 fetch_story.py --check
    python3 fetch_story.py 12345 --out test-cases/12345/story.json
    python3 fetch_story.py https://dev.azure.com/org/proj/_workitems/edit/12345 --format markdown

Exit codes: 0 success, 1 Azure DevOps error, 2 configuration/usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ado_client import API_VERSION, AdoClient, AdoConfig, AdoConfigError, AdoError, html_to_text

STORY_LIKE_TYPES = {"user story", "product backlog item", "requirement", "feature", "bug", "issue", "task"}

RELATION_GROUPS = {
    "System.LinkTypes.Hierarchy-Reverse": "parent",
    "System.LinkTypes.Hierarchy-Forward": "children",
    "System.LinkTypes.Related": "related",
    "System.LinkTypes.Dependency-Forward": "related",
    "System.LinkTypes.Dependency-Reverse": "related",
    "Microsoft.VSTS.Common.TestedBy-Forward": "existing_test_cases",
}

SUMMARY_FIELDS = [
    "System.Id",
    "System.WorkItemType",
    "System.Title",
    "System.State",
    "System.Description",
    "Microsoft.VSTS.Common.AcceptanceCriteria",
    "Microsoft.VSTS.TCM.Steps",
    "Microsoft.VSTS.Common.Priority",
]


def parse_work_item_id(value: str) -> int:
    value = value.strip()
    match = re.search(r"_workitems/edit/(\d+)", value, re.IGNORECASE) or re.fullmatch(
        r"(?:#|AB#)?(\d+)", value, re.IGNORECASE
    )
    if not match:
        raise ValueError(f"'{value}' is not a work item ID or Azure DevOps work item URL.")
    return int(match.group(1))


def _identity(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        return value.get("displayName") or value.get("uniqueName")
    return value or None


def _tags(value: Optional[str]) -> list[str]:
    return [tag.strip() for tag in (value or "").split(";") if tag.strip()]


def _related_id(url: str) -> Optional[int]:
    match = re.search(r"/workItems/(\d+)$", url or "", re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_test_steps(steps_xml: Optional[str]) -> list[dict[str, str]]:
    """Turn Microsoft.VSTS.TCM.Steps XML into [{action, expected}]."""
    if not steps_xml:
        return []
    try:
        root = ET.fromstring(steps_xml)
    except ET.ParseError:
        return [{"action": html_to_text(steps_xml), "expected": ""}]
    steps = []
    for step in root.iter("step"):
        strings = [html_to_text(node.text or "") for node in step.findall("parameterizedString")]
        steps.append({"action": strings[0] if strings else "", "expected": strings[1] if len(strings) > 1 else ""})
    return steps


def summarize(item: dict, config: AdoConfig, detailed: bool) -> dict:
    fields = item.get("fields", {})
    summary = {
        "id": item.get("id"),
        "type": fields.get("System.WorkItemType"),
        "title": fields.get("System.Title"),
        "state": fields.get("System.State"),
        "url": config.web_url(item.get("id")),
    }
    if detailed:
        summary["description"] = html_to_text(fields.get("System.Description"))
        summary["acceptance_criteria"] = html_to_text(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria"))
    if fields.get("System.WorkItemType") == "Test Case":
        summary["priority"] = fields.get("Microsoft.VSTS.Common.Priority")
        summary["steps"] = parse_test_steps(fields.get("Microsoft.VSTS.TCM.Steps"))
    return summary


def normalize(item: dict, related_items: dict[int, dict], comments: list[dict], config: AdoConfig) -> dict:
    fields = item.get("fields", {})
    work_item_id = item["id"]

    work_item = {
        "id": work_item_id,
        "type": fields.get("System.WorkItemType"),
        "title": fields.get("System.Title"),
        "state": fields.get("System.State"),
        "reason": fields.get("System.Reason"),
        "area_path": fields.get("System.AreaPath"),
        "iteration_path": fields.get("System.IterationPath"),
        "priority": fields.get("Microsoft.VSTS.Common.Priority"),
        "severity": fields.get("Microsoft.VSTS.Common.Severity"),
        "story_points": fields.get("Microsoft.VSTS.Scheduling.StoryPoints")
        or fields.get("Microsoft.VSTS.Scheduling.Effort"),
        "value_area": fields.get("Microsoft.VSTS.Common.ValueArea"),
        "tags": _tags(fields.get("System.Tags")),
        "assigned_to": _identity(fields.get("System.AssignedTo")),
        "created_by": _identity(fields.get("System.CreatedBy")),
        "created_date": fields.get("System.CreatedDate"),
        "changed_date": fields.get("System.ChangedDate"),
        "url": config.web_url(work_item_id),
        "description": html_to_text(fields.get("System.Description")),
        "acceptance_criteria": html_to_text(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria")),
        "repro_steps": html_to_text(fields.get("Microsoft.VSTS.TCM.ReproSteps")),
        "system_info": html_to_text(fields.get("Microsoft.VSTS.TCM.SystemInfo")),
    }

    grouped: dict[str, list[dict]] = {"parent": [], "children": [], "related": [], "existing_test_cases": []}
    attachments, hyperlinks = [], []
    for relation in item.get("relations") or []:
        rel = relation.get("rel")
        attributes = relation.get("attributes") or {}
        if rel == "AttachedFile":
            attachments.append({"name": attributes.get("name"), "comment": attributes.get("comment") or ""})
        elif rel == "Hyperlink":
            hyperlinks.append({"url": relation.get("url"), "comment": attributes.get("comment") or ""})
        elif rel in RELATION_GROUPS:
            related_id = _related_id(relation.get("url", ""))
            if related_id is None:
                continue
            group = RELATION_GROUPS[rel]
            linked = related_items.get(related_id)
            if linked is None:
                grouped[group].append({"id": related_id, "note": "not accessible with this PAT or deleted"})
            else:
                grouped[group].append(summarize(linked, config, detailed=group in ("parent", "related")))

    normalized_comments = [
        {
            "author": _identity(comment.get("createdBy")),
            "date": comment.get("createdDate"),
            "text": html_to_text(comment.get("text")),
        }
        for comment in comments
        if not comment.get("isDeleted")
    ]

    return {
        "source": {
            "org_url": config.org_url,
            "project": config.project,
            "api_version": API_VERSION,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "work_item": work_item,
        "parent": grouped["parent"][0] if grouped["parent"] else None,
        "children": grouped["children"],
        "related": grouped["related"],
        "existing_test_cases": grouped["existing_test_cases"],
        "attachments": attachments,
        "hyperlinks": hyperlinks,
        "comments": normalized_comments,
        "warnings": readiness_warnings(work_item, attachments),
    }


def readiness_warnings(work_item: dict, attachments: list[dict]) -> list[str]:
    warnings = []
    if (work_item.get("type") or "").lower() not in STORY_LIKE_TYPES:
        warnings.append(f"Work item type '{work_item.get('type')}' is not a typical requirement type.")
    if not work_item.get("acceptance_criteria"):
        warnings.append("Acceptance Criteria field is empty; requirements must be derived from the description.")
    if not work_item.get("description"):
        warnings.append("Description field is empty.")
    if (work_item.get("state") or "").lower() in {"removed", "closed", "done"}:
        warnings.append(f"Work item is in state '{work_item.get('state')}'.")
    if attachments:
        warnings.append(
            f"{len(attachments)} attachment(s) (mockups/specs) are not downloaded; ask the user for their content if relevant."
        )
    return warnings


def fetch(client: AdoClient, work_item_id: int, include_related: bool, include_comments: bool) -> dict:
    item = client.get_work_item(work_item_id)
    related_items: dict[int, dict] = {}
    if include_related:
        ids = [
            rid
            for relation in item.get("relations") or []
            if relation.get("rel") in RELATION_GROUPS and (rid := _related_id(relation.get("url", ""))) is not None
        ]
        if ids:
            related_items = {wi["id"]: wi for wi in client.get_work_items(ids, SUMMARY_FIELDS)}
    else:
        item = {**item, "relations": [r for r in item.get("relations") or [] if r.get("rel") not in RELATION_GROUPS]}
    comments = client.get_comments(work_item_id) if include_comments else []
    return normalize(item, related_items, comments, client.config)


def to_markdown(story: dict) -> str:
    wi = story["work_item"]
    lines = [
        f"# {wi['type']} {wi['id']}: {wi['title']}",
        "",
        f"- **State:** {wi['state']}  |  **Priority:** {wi['priority']}  |  **Story points:** {wi['story_points']}",
        f"- **Area:** {wi['area_path']}  |  **Iteration:** {wi['iteration_path']}",
        f"- **Tags:** {', '.join(wi['tags']) or '—'}",
        f"- **Link:** {wi['url']}",
        "",
        "## Description",
        wi["description"] or "_(empty)_",
        "",
        "## Acceptance Criteria",
        wi["acceptance_criteria"] or "_(empty)_",
    ]
    if wi.get("repro_steps"):
        lines += ["", "## Repro Steps", wi["repro_steps"]]
    if story["parent"]:
        parent = story["parent"]
        lines += ["", f"## Parent: {parent.get('type')} {parent['id']} — {parent.get('title')}"]
        if parent.get("description"):
            lines.append(parent["description"])
    for heading, key in (("Child items", "children"), ("Related items", "related"), ("Existing test cases", "existing_test_cases")):
        if story[key]:
            lines += ["", f"## {heading}"]
            lines += [
                f"- {i['id']} ({i['note']})" if "note" in i else f"- {i['id']} [{i['type']}] {i['title']} ({i['state']})"
                for i in story[key]
            ]
    if story["attachments"]:
        lines += ["", "## Attachments"] + [f"- {a['name']} {a['comment']}".rstrip() for a in story["attachments"]]
    if story["comments"]:
        lines += ["", "## Discussion"]
        lines += [f"- **{c['author']}** ({c['date']}): {c['text']}" for c in story["comments"]]
    if story["warnings"]:
        lines += ["", "## Warnings"] + [f"- {w}" for w in story["warnings"]]
    return "\n".join(lines) + "\n"


def check_connection(client: AdoClient) -> int:
    project = client.get_project()
    print(f"OK: connected to {client.config.org_url}, project '{project.get('name')}' ({project.get('state')}).")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("work_item", nargs="?", help="Work item ID (12345, #12345, AB#12345) or work item URL")
    parser.add_argument("--check", action="store_true", help="Verify configuration and connectivity, then exit")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--out", type=Path, help="Write output to this file instead of stdout")
    parser.add_argument("--no-related", action="store_true", help="Skip parent/child/related/test-case lookups")
    parser.add_argument("--no-comments", action="store_true", help="Skip discussion comments")
    args = parser.parse_args(argv)

    try:
        client = AdoClient(AdoConfig.from_env())
        if args.check:
            return check_connection(client)
        if not args.work_item:
            parser.error("a work item ID or URL is required (or use --check)")
        work_item_id = parse_work_item_id(args.work_item)
        story = fetch(client, work_item_id, not args.no_related, not args.no_comments)
    except (AdoConfigError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except AdoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(story, indent=2, ensure_ascii=False) if args.format == "json" else to_markdown(story)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + ("\n" if args.format == "json" else ""), encoding="utf-8")
        wi = story["work_item"]
        print(f"Saved {wi['type']} {wi['id']} '{wi['title']}' to {args.out}")
        for warning in story["warnings"]:
            print(f"WARNING: {warning}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())

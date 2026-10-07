"""Unit and integration tests for the manual-test-case-generator skill scripts.

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import copy
import csv
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "manual-test-case-generator"
sys.path.insert(0, str(SKILL / "scripts"))

import ado_client  # noqa: E402
import export_test_cases  # noqa: E402
import fetch_story  # noqa: E402
import publish_test_cases  # noqa: E402
import testcase_schema  # noqa: E402

EXAMPLE = SKILL / "assets" / "example-test-cases.json"


def example_doc() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class HtmlToTextTests(unittest.TestCase):
    def test_paragraphs_breaks_and_entities(self):
        text = ado_client.html_to_text("<div>Hello&nbsp;world<br>next &amp; last</div>")
        self.assertEqual(text, "Hello world\nnext & last")

    def test_ordered_and_nested_lists(self):
        html = "<ol><li>One</li><li>Two<ul><li>Child</li></ul></li></ol>"
        self.assertEqual(ado_client.html_to_text(html), "1. One\n2. Two\n  - Child")

    def test_bold_links_and_tables(self):
        html = '<p><b>Bold</b> <a href="https://x.test">link</a></p><table><tr><td>a</td><td>b</td></tr></table>'
        self.assertEqual(ado_client.html_to_text(html), "**Bold** link (https://x.test)\n| a | b |")

    def test_empty_input(self):
        self.assertEqual(ado_client.html_to_text(None), "")
        self.assertEqual(ado_client.html_to_text(""), "")


class WorkItemIdTests(unittest.TestCase):
    def test_accepted_forms(self):
        for value, expected in [
            ("123", 123),
            ("#45", 45),
            ("AB#67", 67),
            ("https://dev.azure.com/org/My%20Proj/_workitems/edit/89/", 89),
        ]:
            with self.subTest(value=value):
                self.assertEqual(fetch_story.parse_work_item_id(value), expected)

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            fetch_story.parse_work_item_id("story-one")


class StepsXmlTests(unittest.TestCase):
    def test_round_trip_preserves_text_and_special_characters(self):
        steps = [
            {"action": "Type <script> & 'quotes'", "expected": "Shown **literally**"},
            {"action": "Click **Save**", "expected": ""},
        ]
        xml = publish_test_cases.build_steps_xml(steps)
        self.assertIn('last="2"', xml)
        self.assertIn('type="ValidateStep"', xml)
        self.assertIn('type="ActionStep"', xml)
        parsed = fetch_story.parse_test_steps(xml)
        self.assertEqual(parsed[0]["action"], "Type <script> & 'quotes'")
        self.assertEqual(parsed[0]["expected"], "Shown **literally**")
        self.assertEqual(parsed[1], {"action": "Click **Save**", "expected": ""})


class ValidationTests(unittest.TestCase):
    def test_example_is_valid(self):
        report = testcase_schema.validate(example_doc())
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_detects_quality_and_coverage_problems(self):
        doc = example_doc()
        doc["test_cases"][0]["steps"][-1]["expected"] = "It works as expected"
        doc["test_cases"][1]["id"] = "TC-999-002"
        doc["test_cases"][2]["requirement_refs"] = ["AC-99"]
        doc["test_cases"][3]["priority"] = 7
        doc["test_cases"] = [tc for tc in doc["test_cases"] if "AC-5" not in tc["requirement_refs"]]
        report = testcase_schema.validate(doc)
        joined = "\n".join(report.errors)
        self.assertIn("id prefix does not match story id", joined)
        self.assertIn("unknown id 'AC-99'", joined)
        self.assertIn("priority must be an integer 1-4", joined)
        self.assertIn("AC-5 is not covered", joined)
        self.assertTrue(any("vague" in w for w in report.warnings))

    def test_final_step_requires_expected_result(self):
        doc = example_doc()
        doc["test_cases"][0]["steps"][-1]["expected"] = ""
        self.assertIn("final step must have an expected result", "\n".join(testcase_schema.validate(doc).errors))

    def test_untestable_requirement_needs_note(self):
        doc = example_doc()
        doc["requirements"].append({"id": "NFR-1", "text": "Feels fast", "source": "description", "testable": False})
        self.assertIn("NFR-1 is marked untestable", "\n".join(testcase_schema.validate(doc).errors))


class ExportTests(unittest.TestCase):
    def test_exports_markdown_and_ado_csv(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            code = export_test_cases.main([str(EXAMPLE), "--out-dir", tmp])
            self.assertEqual(code, 0)
            markdown = Path(tmp, "1001-test-cases.md").read_text(encoding="utf-8")
            with Path(tmp, "1001-ado-import.csv").open(encoding="utf-8-sig") as handle:
                rows = list(csv.reader(handle))

        self.assertIn("## Requirements traceability matrix", markdown)
        self.assertIn("### TC-1001-008", markdown)
        self.assertEqual(rows[0], export_test_cases.ADO_CSV_COLUMNS)
        case_rows = [r for r in rows[1:] if r[1] == "Test Case"]
        self.assertEqual(len(case_rows), len(example_doc()["test_cases"]))
        self.assertFalse(any("**" in cell for row in rows for cell in row), "Markdown bold must be stripped for ADO")

    def test_invalid_document_exports_nothing(self):
        doc = example_doc()
        doc["test_cases"] = []
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp, "bad.json")
            path.write_text(json.dumps(doc), encoding="utf-8")
            self.assertEqual(export_test_cases.main([str(path)]), 1)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["bad.json"])


class PublishPatchTests(unittest.TestCase):
    def test_patch_contains_fields_tags_and_tests_link(self):
        config = ado_client.AdoConfig("https://dev.azure.com/org", "Proj", "x")
        tc = example_doc()["test_cases"][0]
        patch = publish_test_cases.build_patch(tc, 1001, config, "Proj\\Team", "Proj\\Sprint 1", None)
        by_path = {op["path"]: op["value"] for op in patch}
        self.assertEqual(by_path["/fields/System.Title"], tc["title"])
        self.assertEqual(by_path["/fields/Microsoft.VSTS.Common.Priority"], 1)
        self.assertTrue(by_path["/fields/System.Tags"].startswith("AI-Generated; Story-1001"))
        self.assertEqual(by_path["/relations/-"]["rel"], "Microsoft.VSTS.Common.TestedBy-Reverse")
        self.assertEqual(by_path["/relations/-"]["url"], "https://dev.azure.com/org/_apis/wit/workItems/1001")
        self.assertNotIn("/fields/System.AssignedTo", by_path)

    def test_dry_run_makes_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "test-cases.json")
            path.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(publish_test_cases.main([str(path)]), 0)
            self.assertIn("DRY RUN", out.getvalue())
            self.assertFalse(Path(tmp, "test-cases.published.json").exists())


class DotenvTests(unittest.TestCase):
    def test_loads_values_without_overriding_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp, ".env")
            env_file.write_text('# comment\nexport TCG_A="quoted value"\nTCG_B=from-file\n', encoding="utf-8")
            os.environ["TCG_B"] = "from-env"
            try:
                self.assertEqual(ado_client.load_dotenv(Path(tmp)), env_file.resolve())
                self.assertEqual(os.environ["TCG_A"], "quoted value")
                self.assertEqual(os.environ["TCG_B"], "from-env")
            finally:
                os.environ.pop("TCG_A", None)
                os.environ.pop("TCG_B", None)


# --------------------------------------------------------------------------- #
# Integration: real HTTP against a local fake Azure DevOps
# --------------------------------------------------------------------------- #

STORY = {
    "id": 7,
    "fields": {
        "System.WorkItemType": "User Story",
        "System.Title": "Login",
        "System.State": "Active",
        "System.Tags": "auth; web",
        "System.Description": "<p>As a user I want to log in.</p>",
        "Microsoft.VSTS.Common.AcceptanceCriteria": "<ol><li>Valid login succeeds</li></ol>",
    },
    "relations": [
        {"rel": "System.LinkTypes.Hierarchy-Reverse", "url": "https://x/_apis/wit/workItems/3", "attributes": {}},
        {"rel": "AttachedFile", "url": "https://x/att", "attributes": {"name": "mock.png"}},
    ],
}


class _FakeAdo(BaseHTTPRequestHandler):
    calls: list = []

    def log_message(self, *args):  # silence test output
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        _FakeAdo.calls.append(self.path)
        if self.path.startswith("/org/My%20Proj/_apis/wit/workitems/7?"):
            return self._json(200, STORY)
        if self.path.startswith("/org/My%20Proj/_apis/wit/workItems/7/comments?"):
            return self._json(200, {"comments": [{"createdBy": {"displayName": "PO"}, "text": "<p>Use SSO</p>"}]})
        if self.path.startswith("/org/My%20Proj/_apis/wit/workitems/503?") and _FakeAdo.calls.count(self.path) == 1:
            return self._json(503, {"message": "busy"})
        if self.path.startswith("/org/My%20Proj/_apis/wit/workitems/503?"):
            return self._json(200, {**STORY, "id": 503, "relations": []})
        return self._json(404, {"message": "missing"})

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        self.rfile.read(length)
        parent = {"id": 3, "fields": {"System.WorkItemType": "Feature", "System.Title": "Auth", "System.State": "New"}}
        return self._json(200, {"value": [parent]})


class AdoClientIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _FakeAdo)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{cls.server.server_port}/org"
        cls.client = ado_client.AdoClient(ado_client.AdoConfig(url, "My Proj", "token"))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_fetch_normalizes_story_parent_comments_and_attachments(self):
        story = fetch_story.fetch(self.client, 7, include_related=True, include_comments=True)
        self.assertEqual(story["work_item"]["acceptance_criteria"], "1. Valid login succeeds")
        self.assertEqual(story["work_item"]["tags"], ["auth", "web"])
        self.assertEqual(story["parent"]["title"], "Auth")
        self.assertEqual(story["comments"][0]["text"], "Use SSO")
        self.assertEqual(story["attachments"], [{"name": "mock.png", "comment": ""}])
        self.assertTrue(any("attachment" in w for w in story["warnings"]))

    def test_not_found_maps_to_helpful_error(self):
        with self.assertRaises(ado_client.AdoError) as ctx:
            self.client.get_work_item(999)
        self.assertIn("HTTP 404", str(ctx.exception))
        self.assertIn("missing", str(ctx.exception))

    def test_retries_transient_server_errors(self):
        original_sleep = ado_client.time.sleep
        ado_client.time.sleep = lambda _seconds: None
        try:
            self.assertEqual(self.client.get_work_item(503)["id"], 503)
        finally:
            ado_client.time.sleep = original_sleep


class ConfigTests(unittest.TestCase):
    def test_rejects_plain_http_and_missing_values(self):
        saved = {k: os.environ.get(k) for k in ("ADO_ORG_URL", "ADO_PROJECT", "ADO_PAT", "ADO_ENV_FILE")}
        try:
            os.environ["ADO_ENV_FILE"] = os.devnull
            os.environ.update({"ADO_ORG_URL": "http://insecure", "ADO_PROJECT": "P", "ADO_PAT": "x"})
            with self.assertRaises(ado_client.AdoConfigError):
                ado_client.AdoConfig.from_env()
            os.environ["ADO_PAT"] = ""
            with self.assertRaisesRegex(ado_client.AdoConfigError, "ADO_PAT"):
                ado_client.AdoConfig.from_env()
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()

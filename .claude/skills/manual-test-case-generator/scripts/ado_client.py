"""Dependency-free Azure DevOps REST client shared by the skill's scripts.

Only the Python standard library is used so the skill works on any machine
with Python 3.9+ and no `pip install` step.

Configuration (environment variables, or a `.env` file in the current
directory or any parent directory):

    ADO_ORG_URL   e.g. https://dev.azure.com/contoso
    ADO_PROJECT   e.g. Payments Platform
    ADO_PAT       Personal Access Token (never logged or printed)
    ADO_ENV_FILE  optional explicit path to a .env file
"""

from __future__ import annotations

import base64
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Optional

API_VERSION = "7.1"
COMMENTS_API_VERSION = "7.1-preview.4"
DEFAULT_TIMEOUT_SECONDS = 30
MAX_RETRIES = 4
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
BATCH_LIMIT = 200  # Azure DevOps maximum ids per workitemsbatch call
USER_AGENT = "manual-test-case-generator-skill/1.0"


class AdoError(Exception):
    """Any failure talking to Azure DevOps."""


class AdoConfigError(AdoError):
    """Missing or invalid local configuration."""


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


def load_dotenv(start: Optional[Path] = None) -> Optional[Path]:
    """Load KEY=VALUE pairs from the nearest .env file without overriding
    variables that are already set in the environment. Returns the file used."""
    explicit = os.environ.get("ADO_ENV_FILE")
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    else:
        here = (start or Path.cwd()).resolve()
        candidates.extend(directory / ".env" for directory in (here, *here.parents))

    for path in candidates:
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            os.environ.setdefault(key, value)
        return path
    return None


@dataclass(frozen=True)
class AdoConfig:
    org_url: str
    project: str
    pat: str

    @classmethod
    def from_env(cls) -> "AdoConfig":
        load_dotenv()
        org_url = os.environ.get("ADO_ORG_URL", "").strip().rstrip("/")
        project = os.environ.get("ADO_PROJECT", "").strip()
        pat = os.environ.get("ADO_PAT", "").strip()

        missing = [
            name
            for name, value in (("ADO_ORG_URL", org_url), ("ADO_PROJECT", project), ("ADO_PAT", pat))
            if not value
        ]
        if missing:
            raise AdoConfigError(
                "Missing Azure DevOps configuration: "
                + ", ".join(missing)
                + ". Copy .env.example to .env in the project root and fill it in."
            )
        if not org_url.startswith("https://"):
            raise AdoConfigError(
                "ADO_ORG_URL must be an https URL such as https://dev.azure.com/<organization>."
            )
        return cls(org_url=org_url, project=project, pat=pat)

    def web_url(self, work_item_id: int) -> str:
        return f"{self.org_url}/{urllib.parse.quote(self.project)}/_workitems/edit/{work_item_id}"

    def api_work_item_url(self, work_item_id: int) -> str:
        return f"{self.org_url}/_apis/wit/workItems/{work_item_id}"


# --------------------------------------------------------------------------- #
# HTTP client
# --------------------------------------------------------------------------- #


class AdoClient:
    def __init__(self, config: AdoConfig, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.config = config
        self.timeout = timeout
        token = base64.b64encode(f":{config.pat}".encode("utf-8")).decode("ascii")
        self._base_headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        self._ssl_context = build_ssl_context()

    # -- low level ---------------------------------------------------------- #

    def _url(
        self, path: str, params: Optional[dict[str, Any]], project_scoped: bool, api_version: str
    ) -> str:
        base = self.config.org_url
        if project_scoped:
            base = f"{base}/{urllib.parse.quote(self.config.project)}"
        query: dict[str, Any] = {"api-version": api_version}
        if params:
            query.update({k: v for k, v in params.items() if v is not None})
        return f"{base}/{path.lstrip('/')}?{urllib.parse.urlencode(query, safe='$,')}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        body: Any = None,
        content_type: str = "application/json",
        project_scoped: bool = True,
        api_version: str = API_VERSION,
    ) -> Any:
        url = self._url(path, params, project_scoped, api_version)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = dict(self._base_headers)
        if data is not None:
            headers["Content-Type"] = content_type

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_context) as resp:
                    raw = resp.read()
                    ctype = resp.headers.get("Content-Type", "")
                    # A bad/expired PAT often yields 203 + an HTML sign-in page.
                    if resp.status == 203 or "text/html" in ctype:
                        raise AdoError(
                            "Authentication failed (Azure DevOps returned a sign-in page). "
                            "Check that ADO_PAT is valid, not expired, and belongs to ADO_ORG_URL."
                        )
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                if exc.code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                    time.sleep(_retry_delay(exc, attempt))
                    last_error = exc
                    continue
                raise AdoError(_describe_http_error(exc, method, path)) from None
            except urllib.error.URLError as exc:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                    last_error = exc
                    continue
                reason = exc.reason
                if isinstance(reason, ssl.SSLCertVerificationError):
                    raise AdoError(
                        f"Could not reach {self.config.org_url}: TLS certificate verification failed ({reason.verify_message}). "
                        "Python has no trusted root certificates. On macOS with python.org Python, run "
                        "'/Applications/Python 3.x/Install Certificates.command', or `pip install certifi`. "
                        "Behind a corporate proxy, set SSL_CERT_FILE to your company's CA bundle."
                    ) from None
                raise AdoError(f"Could not reach {self.config.org_url}: {reason}") from None
        raise AdoError(f"Request failed after {MAX_RETRIES} retries: {last_error}")

    # -- endpoints ---------------------------------------------------------- #

    def get_project(self) -> dict:
        path = f"_apis/projects/{urllib.parse.quote(self.config.project)}"
        return self.request("GET", path, project_scoped=False)

    def get_work_item(self, work_item_id: int) -> dict:
        return self.request("GET", f"_apis/wit/workitems/{work_item_id}", params={"$expand": "relations"})

    def get_work_items(self, ids: Iterable[int], fields: Optional[list[str]] = None) -> list[dict]:
        unique_ids = list(dict.fromkeys(int(i) for i in ids))
        results: list[dict] = []
        for start in range(0, len(unique_ids), BATCH_LIMIT):
            chunk = unique_ids[start:start + BATCH_LIMIT]
            body: dict[str, Any] = {"ids": chunk, "errorPolicy": "omit"}
            if fields:
                body["fields"] = fields
            payload = self.request("POST", "_apis/wit/workitemsbatch", body=body)
            results.extend(item for item in payload.get("value", []) if item)
        return results

    def get_comments(self, work_item_id: int, top: int = 200) -> list[dict]:
        url_path = f"_apis/wit/workItems/{work_item_id}/comments"
        comments: list[dict] = []
        token: Optional[str] = None
        while True:
            params = {"$top": top, "order": "asc", "continuationToken": token}
            # The comments API is still preview-versioned.
            payload = self.request("GET", url_path, params=params, api_version=COMMENTS_API_VERSION)
            comments.extend(payload.get("comments", []))
            token = payload.get("continuationToken")
            if not token:
                return comments

    def create_work_item(self, work_item_type: str, patch: list[dict]) -> dict:
        path = f"_apis/wit/workitems/${urllib.parse.quote(work_item_type)}"
        return self.request("POST", path, body=patch, content_type="application/json-patch+json")

    def add_test_cases_to_suite(self, plan_id: int, suite_id: int, test_case_ids: list[int]) -> Any:
        path = f"_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestCase"
        body = [{"workItem": {"id": tc_id}} for tc_id in test_case_ids]
        return self.request("POST", path, body=body)


def build_ssl_context() -> ssl.SSLContext:
    """Default TLS context, falling back to certifi's CA bundle when Python's
    own store is empty (common with python.org installers on macOS whose
    'Install Certificates' step was never run). Certificates are always
    verified; this only chooses where trusted roots come from."""
    context = ssl.create_default_context()
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return context
    if context.cert_store_stats().get("x509_ca", 0) == 0:
        try:
            import certifi  # optional; widely preinstalled
        except ImportError:
            return context
        context.load_verify_locations(cafile=certifi.where())
    return context


def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> float:
    retry_after = exc.headers.get("Retry-After") if exc.headers else None
    if retry_after and retry_after.isdigit():
        return min(float(retry_after), 60.0)
    return float(2 ** attempt)


def _describe_http_error(exc: urllib.error.HTTPError, method: str, path: str) -> str:
    detail = ""
    try:
        payload = json.loads(exc.read() or b"{}")
        detail = payload.get("message", "")
    except (ValueError, AttributeError):
        pass
    hints = {
        400: "The request was rejected. Check field names, area/iteration paths and values.",
        401: "Authentication failed. ADO_PAT is invalid or expired.",
        403: "Access denied. The PAT is missing a required scope (see references/ado-setup.md).",
        404: "Not found. Check the work item ID, ADO_PROJECT and ADO_ORG_URL.",
    }
    hint = hints.get(exc.code, "Unexpected response from Azure DevOps.")
    message = f"HTTP {exc.code} on {method} {path.split('?')[0]}: {hint}"
    return f"{message} Server said: {detail}" if detail else message


# --------------------------------------------------------------------------- #
# HTML -> readable text
# --------------------------------------------------------------------------- #

_BLOCK_TAGS = {"p", "div", "section", "article", "header", "footer", "blockquote", "pre", "table", "tr"}
_HEADING_TAGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}


class _HtmlToText(HTMLParser):
    """Converts Azure DevOps rich-text (HTML) fields into Markdown-like text,
    preserving the structure that matters for test design: paragraphs,
    ordered/unordered lists, tables, links and image placeholders."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.list_stack: list[list[Any]] = []  # [kind, counter]
        self.href_stack: list[Optional[str]] = []
        self.in_pre = False
        self.cell_index = 0

    def _newline(self, count: int = 1) -> None:
        text = "".join(self.out)
        trailing = len(text) - len(text.rstrip("\n"))
        if text and trailing < count:
            self.out.append("\n" * (count - trailing))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attributes = dict(attrs)
        if tag in _HEADING_TAGS:
            self._newline(2)
            self.out.append(_HEADING_TAGS[tag] + " ")
        elif tag in _BLOCK_TAGS:
            self._newline(1)
            if tag == "pre":
                self.in_pre = True
            if tag == "tr":
                self.cell_index = 0
        elif tag == "br":
            self.out.append("\n")
        elif tag in ("ul", "ol"):
            self._newline(1)
            self.list_stack.append([tag, 0])
        elif tag == "li":
            self._newline(1)
            indent = "  " * max(len(self.list_stack) - 1, 0)
            if self.list_stack and self.list_stack[-1][0] == "ol":
                self.list_stack[-1][1] += 1
                self.out.append(f"{indent}{self.list_stack[-1][1]}. ")
            else:
                self.out.append(f"{indent}- ")
        elif tag in ("td", "th"):
            self.out.append("| " if self.cell_index == 0 else " | ")
            self.cell_index += 1
        elif tag == "a":
            self.href_stack.append(attributes.get("href"))
        elif tag == "img":
            alt = attributes.get("alt") or "image"
            self.out.append(f"[{alt}]")
        elif tag in ("b", "strong"):
            self.out.append("**")
        elif tag in ("i", "em"):
            self.out.append("_")

    def handle_endtag(self, tag: str) -> None:
        if tag in _HEADING_TAGS or tag in _BLOCK_TAGS:
            if tag == "tr" and self.cell_index:
                self.out.append(" |")
            if tag == "pre":
                self.in_pre = False
            self._newline(1)
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            self._newline(1)
        elif tag == "a":
            href = self.href_stack.pop() if self.href_stack else None
            if href and not href.startswith("#"):
                self.out.append(f" ({href})")
        elif tag in ("b", "strong"):
            self.out.append("**")
        elif tag in ("i", "em"):
            self.out.append("_")

    def handle_data(self, data: str) -> None:
        if self.in_pre:
            self.out.append(data)
        else:
            self.out.append(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        raw = "".join(self.out).replace(" ", " ")
        lines = [line.rstrip() for line in raw.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"\*\*\s*\*\*", "", cleaned)
        return cleaned.strip()


def html_to_text(html_value: Optional[str]) -> str:
    if not html_value:
        return ""
    parser = _HtmlToText()
    parser.feed(html_value)
    parser.close()
    return parser.text()

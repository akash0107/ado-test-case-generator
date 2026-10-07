# Azure DevOps Setup and Troubleshooting

## 1. Create a Personal Access Token (PAT)

1. In Azure DevOps, open **User settings** (top right) → **Personal access tokens** → **New Token**.
2. **Organization:** the one that contains your project.
3. **Expiration:** as short as practical (e.g. 30 days).
4. **Scopes:** choose **Custom defined** and grant only what you need:

| Capability | Scope required |
|---|---|
| Read stories (`fetch_story.py`) | **Work Items → Read** |
| Create Test Case work items (`publish_test_cases.py --apply`) | **Work Items → Read & write** |
| Add test cases to a Test Plan suite (`--plan-id/--suite-id`) | **Test Management → Read & write** |
| Connectivity check (`--check`) | **Project and Team → Read** (optional) |

5. Copy the token. Azure DevOps shows it only once.

## 2. Configure the project

Copy `.env.example` to `.env` in the project root and fill it in:

```dotenv
ADO_ORG_URL=https://dev.azure.com/your-organization
ADO_PROJECT=Your Project Name
ADO_PAT=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- `.env` is listed in `.gitignore`. **Never commit it.**
- Older organizations may use `https://<org>.visualstudio.com`. That form also works.
- Project names may contain spaces. Do not URL-encode them yourself.
- Environment variables that are already set take precedence over `.env`.
  `ADO_ENV_FILE=/path/to/file` points the scripts at a different file.

Verify the setup:

```bash
python3 .claude/skills/manual-test-case-generator/scripts/fetch_story.py --check
```

## 3. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Missing Azure DevOps configuration: ADO_PAT` | No `.env` file, or the variable is empty | Create `.env` in the project root |
| `Authentication failed (… sign-in page)` / HTTP 401 | PAT is invalid, expired, or from another organization | Regenerate the PAT for the correct organization |
| HTTP 403 | PAT is missing a scope | Add the scope from the table above |
| HTTP 404 on a work item | Wrong ID, or the item belongs to a different project | Check `ADO_PROJECT`; open the item in the browser |
| HTTP 400 on publish, mentioning AreaPath/IterationPath | Path does not exist | Pass `--area-path` / `--iteration-path` with valid values |
| HTTP 429 / 5xx | Throttling or service issue | The client retries with backoff automatically; rerun later |
| `CERTIFICATE_VERIFY_FAILED` / `TLS certificate verification failed` | Python has no root certificates (python.org installer on macOS) or a corporate proxy re-signs TLS | Run `/Applications/Python 3.x/Install Certificates.command` or `pip install certifi` (the client uses certifi automatically). Behind a proxy, set `SSL_CERT_FILE` to the company CA bundle |
| `Could not reach …` | Network, VPN, or proxy | Check connectivity; set `HTTPS_PROXY` if you are behind a proxy |

## 4. Importing the CSV manually (no write scope needed)

> **Use Test Plans, not Boards.** **Boards → Work items → Import Work Items** rejects
> this file with `Invalid column headers: Test Step, Step Action, Step Expected`, because
> Boards CSV import cannot create test steps. The CSV import inside **Test Plans** needs
> an existing test plan, and **creating a test plan requires the "Basic + Test Plans"
> access level** (paid, or a 30-day trial). Without that licence, use
> `publish_test_cases.py` instead: it creates Test Case work items through the Work Items
> API, so no test plan is needed.

1. **Test Plans** → open the plan → select a suite.
2. **⋯** → **Import test cases from CSV**. In some versions this appears as
   **New Test Case → Import from CSV**.
3. Choose `<storyId>-ado-import.csv`, check the column mapping, and import.
4. Link the imported cases to the story (**Tests** link type), or use
   `publish_test_cases.py`, which links them automatically.

## 5. APIs used

| Purpose | Endpoint (api-version 7.1) |
|---|---|
| Work item with relations | `GET {org}/{project}/_apis/wit/workitems/{id}?$expand=relations` |
| Linked items, batched | `POST {org}/{project}/_apis/wit/workitemsbatch` |
| Discussion comments | `GET {org}/{project}/_apis/wit/workItems/{id}/comments` (7.1-preview.4) |
| Create test case | `POST {org}/{project}/_apis/wit/workitems/$Test%20Case` (JSON Patch) |
| Add to suite | `POST {org}/{project}/_apis/testplan/Plans/{plan}/Suites/{suite}/TestCase` |
| Connectivity | `GET {org}/_apis/projects/{project}` |

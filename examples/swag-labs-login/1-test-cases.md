# Test Specification — Story 1: Swag Labs login functionality

| Item | Value |
|---|---|
| Story | [1](https://dev.azure.com/learnbydoing1/AIAgentsLearning/_workitems/edit/1) |
| Generated | 2026-10-07 |
| Author | QA (AI-assisted) |
| Status | Draft — pending review |
| Total test cases | 15 |
| By priority | P1 - Critical: 5, P2 - High: 6, P3 - Medium: 4 |
| By type | Functional: 2, Negative: 7, Security: 4, UI: 1, Usability: 1 |

## Scope

Covers authentication on the Swag Labs (https://www.saucedemo.com/) login page: page elements, valid login and redirect to /inventory.html, invalid and missing credentials, the locked-out user, password masking, error visibility, and blocking direct access to the inventory page without a session. Username × password inputs were modelled as a decision table (each Valid / Invalid / Empty → 9 combinations); the story's ACs define 7 combinations, and the remaining 2 (Invalid username + Empty password, Empty username + Invalid password) are covered in TC-1-008 and TC-1-007. Main risks: unauthorized access to the inventory, and unclear or missing error feedback.

## Out of scope

- Logout, session timeout and 'remember me' behaviour (not part of this story)
- Behaviour of other Swag Labs demo users after login (problem_user, performance_glitch_user, error_user, visual_user); they belong to inventory/checkout stories
- Content and functionality of the Products/Inventory page beyond confirming the redirect
- Password reset or account registration (the application provides neither)
- Automated (Playwright) implementation; the story's automation note is for a separate task
- Cross-browser and mobile-device matrix (no compatibility requirement stated)

## Requirements traceability matrix

| Req ID | Source | Requirement | Test cases | Status |
|---|---|---|---|---|
| AC-1 | description | A user with valid credentials who clicks Login is authenticated and redirected to the Products page, and the URL contains /inventory.html. | TC-1-001, TC-1-014, TC-1-015 | Covered |
| AC-2 | description | An invalid username with a valid password fails authentication; the user remains on the login page and an error message is displayed. | TC-1-002 | Covered |
| AC-3 | description | A valid username with an invalid password fails authentication and an error message is displayed. | TC-1-003 | Covered |
| AC-4 | description | An invalid username with an invalid password fails authentication; the user remains on the login page and an authentication error is displayed. | TC-1-006 | Covered |
| AC-5 | description | With an empty username and a password entered, login does not proceed and 'Epic sadface: Username is required' is displayed. | TC-1-007 | Covered |
| AC-6 | description | With a username entered and an empty password, login does not proceed and 'Epic sadface: Password is required' is displayed. | TC-1-008 | Covered |
| AC-7 | description | With both fields empty, login does not proceed and the username-required message is displayed. | TC-1-009 | Covered |
| AC-8 | description | A locked user entering valid credentials is rejected and a locked-user error message is displayed. | TC-1-004 | Covered |
| REQ-1 | description | The login page contains a Username field, a Password field and a Login button. | TC-1-001 | Covered |
| REQ-2 | description | Password characters are not displayed as plain text while being entered (Business Rule 6). | TC-1-010 | Covered |
| REQ-3 | description | Invalid or missing credentials must not provide access to the inventory page (Business Rules 2, 3, 5). | TC-1-002, TC-1-003, TC-1-004, TC-1-005, TC-1-006, TC-1-007, TC-1-008, TC-1-011 | Covered |
| REQ-4 | description | Authentication errors are clearly visible to the user (Business Rule 7). | TC-1-012 | Covered |
| IMP-1 | implicit | Credentials are matched exactly: a username differing in letter case or surrounding whitespace is not accepted. | TC-1-013 | Covered |
| IMP-2 | implicit | Pressing Enter in the Password field submits the login form. | TC-1-014 | Covered |
| IMP-3 | implicit | A user can log in successfully with valid credentials immediately after a failed attempt. | TC-1-015 | Covered |

## Assumptions

- Acceptance criteria are taken from the Description field because the ADO Acceptance Criteria field is empty; AC numbering follows the story (AC1–AC8 → AC-1–AC-8).
- Test environment is the public Swag Labs demo at https://www.saucedemo.com/ with its published demo accounts: standard_user and locked_out_user, password secret_sauce.
- Where the story says only 'an appropriate error message' (AC-2, AC-3, AC-4, AC-8), expected texts use the current Swag Labs messages: 'Epic sadface: Username and password do not match any user in this service' and 'Epic sadface: Sorry, this user has been locked out.'
- AC-3 does not state that the user remains on the login page; this is assumed, consistent with AC-2 and AC-4 and Business Rule 3.
- REQ-3: opening /inventory.html without logging in redirects to the login page and shows 'Epic sadface: You can only access '/inventory.html' when you are logged in.' (current application behaviour; not specified in the story).
- REQ-4: 'clearly visible' is interpreted as an error banner shown above the Login button without scrolling, with both input fields marked with an error icon, and a close (✖) button that dismisses the banner (current application design).
- IMP-1: usernames are case-sensitive and surrounding spaces are not trimmed (standard for this application; not stated in the story).
- IMP-2: Enter-key submission is a standard expectation of HTML login forms; not stated in the story.
- IMP-3: no lockout after a single failed attempt; the story defines locking only as an account configuration (AC-8).

## Open questions (for PO / Dev)

1. The ADO Acceptance Criteria field is empty and the ACs are inside the Description. Should they be moved to the Acceptance Criteria field so they can be traced and reported on?
2. AC-2, AC-3, AC-4 and AC-8 say 'appropriate error message' without exact text. Are the current Swag Labs messages (see assumptions) the approved wording?
3. Should the username be case-insensitive or have surrounding whitespace trimmed? TC-1-013 currently expects both to be rejected.
4. Is there a limit on failed login attempts (e.g. temporary lockout after N tries)? The story mentions only pre-configured locked accounts.

## Test case index

| ID | Title | Type | Priority | Technique | Covers |
|---|---|---|---|---|---|
| [TC-1-001](#tc-1-001) | Verify standard user logs in and is redirected to the Products page | Functional | P1 | Use Case / Scenario | AC-1, REQ-1 |
| [TC-1-002](#tc-1-002) | Reject login with an unregistered username and a valid password | Negative | P1 | Equivalence Partitioning | AC-2, REQ-3 |
| [TC-1-003](#tc-1-003) | Reject login with a valid username and an incorrect password | Negative | P1 | Equivalence Partitioning | AC-3, REQ-3 |
| [TC-1-004](#tc-1-004) | Reject login for a locked-out user with valid credentials | Security | P1 | Equivalence Partitioning | AC-8, REQ-3 |
| [TC-1-005](#tc-1-005) | Prevent direct access to the inventory page without logging in | Security | P1 | Error Guessing | REQ-3 |
| [TC-1-006](#tc-1-006) | Reject login when both username and password are invalid | Negative | P2 | Decision Table | AC-4, REQ-3 |
| [TC-1-007](#tc-1-007) | Display 'Username is required' when username is empty and password is entered | Negative | P2 | Decision Table | AC-5, REQ-3 |
| [TC-1-008](#tc-1-008) | Display 'Password is required' when password is empty and username is entered | Negative | P2 | Decision Table | AC-6, REQ-3 |
| [TC-1-009](#tc-1-009) | Display 'Username is required' when both fields are empty | Negative | P2 | Decision Table | AC-7 |
| [TC-1-010](#tc-1-010) | Verify password characters are masked while typing | Security | P2 | Checklist | REQ-2 |
| [TC-1-011](#tc-1-011) | Reject SQL-injection and script strings in login fields without granting access | Security | P2 | Error Guessing | REQ-3 |
| [TC-1-012](#tc-1-012) | Display authentication errors prominently near the login form | UI | P3 | Checklist | REQ-4 |
| [TC-1-013](#tc-1-013) | Reject username with different letter case or surrounding spaces | Negative | P3 | Error Guessing | IMP-1 |
| [TC-1-014](#tc-1-014) | Allow login by pressing Enter in the Password field | Usability | P3 | Use Case / Scenario | IMP-2, AC-1 |
| [TC-1-015](#tc-1-015) | Allow successful login immediately after a failed attempt | Functional | P3 | Error Guessing | IMP-3, AC-1 |

## Test cases

### TC-1-001

**Verify standard user logs in and is redirected to the Products page**

| Field | Value |
|---|---|
| Objective | Confirm the main success path: a registered user with valid credentials reaches the inventory page. |
| Type | Functional |
| Priority | P1 - Critical |
| Design technique | Use Case / Scenario |
| Requirements | AC-1, REQ-1 |
| Tags | smoke, e2e |

**Preconditions**

- Browser is open with no active Swag Labs session (cookies cleared or private window).

**Test data**

| Name | Value |
|---|---|
| URL | `https://www.saucedemo.com/` |
| Username | `standard_user` |
| Password | `secret_sauce` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Navigate to https://www.saucedemo.com/. | The Swag Labs login page is displayed with a **Username** field, a **Password** field and a **Login** button. |
| 2 | Enter 'standard_user' in **Username**. | — |
| 3 | Enter 'secret_sauce' in **Password**. | — |
| 4 | Click **Login**. | The browser URL changes to https://www.saucedemo.com/inventory.html. |
| 5 | Observe the page content. | The page header shows 'Products', the product list is displayed, and no error message is shown. |

### TC-1-002

**Reject login with an unregistered username and a valid password**

| Field | Value |
|---|---|
| Objective | Verify that an invalid username alone causes authentication to fail without granting access. |
| Type | Negative |
| Priority | P1 - Critical |
| Design technique | Equivalence Partitioning |
| Requirements | AC-2, REQ-3 |
| Tags | regression |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| Username | `invalid_user` |
| Password | `secret_sauce` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter 'invalid_user' in **Username** and 'secret_sauce' in **Password**. | — |
| 2 | Click **Login**. | The error 'Epic sadface: Username and password do not match any user in this service' is displayed. |
| 3 | Check the browser URL and page content. | The URL remains https://www.saucedemo.com/ and the Products page is not displayed. |

### TC-1-003

**Reject login with a valid username and an incorrect password**

| Field | Value |
|---|---|
| Objective | Verify that a wrong password for an existing account causes authentication to fail without granting access. |
| Type | Negative |
| Priority | P1 - Critical |
| Design technique | Equivalence Partitioning |
| Requirements | AC-3, REQ-3 |
| Tags | regression |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| Username | `standard_user` |
| Password | `wrong_password` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter 'standard_user' in **Username** and 'wrong_password' in **Password**. | — |
| 2 | Click **Login**. | The error 'Epic sadface: Username and password do not match any user in this service' is displayed. |
| 3 | Check the browser URL and page content. | The URL remains https://www.saucedemo.com/ and the Products page is not displayed. |

### TC-1-004

**Reject login for a locked-out user with valid credentials**

| Field | Value |
|---|---|
| Objective | Ensure an account configured as locked cannot access the application even with the correct password. |
| Type | Security |
| Priority | P1 - Critical |
| Design technique | Equivalence Partitioning |
| Requirements | AC-8, REQ-3 |
| Tags | security, regression |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.
- Account 'locked_out_user' is configured as locked (default in the Swag Labs demo).

**Test data**

| Name | Value |
|---|---|
| Username | `locked_out_user` |
| Password | `secret_sauce` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter 'locked_out_user' in **Username** and 'secret_sauce' in **Password**. | — |
| 2 | Click **Login**. | The error 'Epic sadface: Sorry, this user has been locked out.' is displayed. |
| 3 | Check the browser URL and page content. | The URL remains https://www.saucedemo.com/ and the Products page is not displayed. |

### TC-1-005

**Prevent direct access to the inventory page without logging in**

| Field | Value |
|---|---|
| Objective | Verify the inventory page cannot be reached by URL without an authenticated session. |
| Type | Security |
| Priority | P1 - Critical |
| Design technique | Error Guessing |
| Requirements | REQ-3 |
| Tags | security |

**Preconditions**

- Browser has no active Swag Labs session (cookies cleared or new private window).

**Test data**

| Name | Value |
|---|---|
| URL | `https://www.saucedemo.com/inventory.html` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Navigate directly to https://www.saucedemo.com/inventory.html. | The login page is displayed instead of the Products page. |
| 2 | Observe the error area above the **Login** button. | The error "Epic sadface: You can only access '/inventory.html' when you are logged in." is displayed and no product list is visible. |

### TC-1-006

**Reject login when both username and password are invalid**

| Field | Value |
|---|---|
| Objective | Verify authentication fails when neither credential matches an account. |
| Type | Negative |
| Priority | P2 - High |
| Design technique | Decision Table |
| Requirements | AC-4, REQ-3 |
| Tags | regression |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| Username | `invalid_user` |
| Password | `invalid_pass` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter 'invalid_user' in **Username** and 'invalid_pass' in **Password**. | — |
| 2 | Click **Login**. | The error 'Epic sadface: Username and password do not match any user in this service' is displayed. |
| 3 | Check the browser URL and page content. | The URL remains https://www.saucedemo.com/ and the Products page is not displayed. |

### TC-1-007

**Display 'Username is required' when username is empty and password is entered**

| Field | Value |
|---|---|
| Objective | Verify the mandatory-username rule applies whether the entered password is valid or invalid (decision table: Empty username × Valid / Invalid password). |
| Type | Negative |
| Priority | P2 - High |
| Design technique | Decision Table |
| Requirements | AC-5, REQ-3 |
| Tags | validation |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| Valid password | `secret_sauce` |
| Invalid password | `invalid_pass` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Leave **Username** empty, enter 'secret_sauce' in **Password** and click **Login**. | The error 'Epic sadface: Username is required' is displayed and the URL remains https://www.saucedemo.com/. |
| 2 | Reload the page. Leave **Username** empty, enter 'invalid_pass' in **Password** and click **Login**. | The error 'Epic sadface: Username is required' is displayed and the URL remains https://www.saucedemo.com/. |

### TC-1-008

**Display 'Password is required' when password is empty and username is entered**

| Field | Value |
|---|---|
| Objective | Verify the mandatory-password rule applies whether the entered username is valid or invalid (decision table: Valid / Invalid username × Empty password). |
| Type | Negative |
| Priority | P2 - High |
| Design technique | Decision Table |
| Requirements | AC-6, REQ-3 |
| Tags | validation |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| Valid username | `standard_user` |
| Invalid username | `invalid_user` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter 'standard_user' in **Username**, leave **Password** empty and click **Login**. | The error 'Epic sadface: Password is required' is displayed and the URL remains https://www.saucedemo.com/. |
| 2 | Reload the page. Enter 'invalid_user' in **Username**, leave **Password** empty and click **Login**. | The error 'Epic sadface: Password is required' is displayed and the URL remains https://www.saucedemo.com/. |

### TC-1-009

**Display 'Username is required' when both fields are empty**

| Field | Value |
|---|---|
| Objective | Verify that with no input the username validation takes precedence and login does not proceed. |
| Type | Negative |
| Priority | P2 - High |
| Design technique | Decision Table |
| Requirements | AC-7 |
| Tags | validation |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session; both fields are empty.

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Without entering anything, click **Login**. | The error 'Epic sadface: Username is required' is displayed; 'Password is required' is not shown. |
| 2 | Check the browser URL. | The URL remains https://www.saucedemo.com/. |

### TC-1-010

**Verify password characters are masked while typing**

| Field | Value |
|---|---|
| Objective | Ensure the password is never displayed as plain text on screen. |
| Type | Security |
| Priority | P2 - High |
| Design technique | Checklist |
| Requirements | REQ-2 |
| Tags | security |

**Preconditions**

- Browser is on https://www.saucedemo.com/.

**Test data**

| Name | Value |
|---|---|
| Password | `secret_sauce` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Click in **Password** and type 'secret_sauce'. | Each typed character appears as a masking symbol (• or *); the text 'secret_sauce' is not readable on screen. |
| 2 | Open browser developer tools and inspect the **Password** input element. | The input has the attribute type="password". |

### TC-1-011

**Reject SQL-injection and script strings in login fields without granting access**

| Field | Value |
|---|---|
| Objective | Probe common injection inputs to confirm they are treated as ordinary invalid credentials. |
| Type | Security |
| Priority | P2 - High |
| Design technique | Error Guessing |
| Requirements | REQ-3 |
| Tags | security |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| SQL injection | `' OR '1'='1` |
| Script injection | `<script>alert('xss')</script>` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter ' OR '1'='1 in both **Username** and **Password** and click **Login**. | The error 'Epic sadface: Username and password do not match any user in this service' is displayed and the URL remains https://www.saucedemo.com/. |
| 2 | Reload the page. Enter <script>alert('xss')</script> in **Username**, 'secret_sauce' in **Password** and click **Login**. | No browser alert pop-up appears; the 'Username and password do not match any user in this service' error is displayed and the URL remains https://www.saucedemo.com/. |

### TC-1-012

**Display authentication errors prominently near the login form**

| Field | Value |
|---|---|
| Objective | Verify error feedback is easy to notice and is associated with the input fields. |
| Type | UI |
| Priority | P3 - Medium |
| Design technique | Checklist |
| Requirements | REQ-4 |
| Tags | ui |

**Preconditions**

- Browser window is 1366×768 or larger, on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| Username | `invalid_user` |
| Password | `invalid_pass` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter 'invalid_user' / 'invalid_pass' and click **Login**. | An error banner with a red background appears directly above the **Login** button and is fully visible without scrolling. |
| 2 | Look at the **Username** and **Password** fields. | Both fields display an error (✖) icon and a red underline. |
| 3 | Click the close (✖) button on the error banner. | The banner disappears, the field error icons are removed, and the entered values remain in the fields. |

### TC-1-013

**Reject username with different letter case or surrounding spaces**

| Field | Value |
|---|---|
| Objective | Verify credentials are matched exactly, so near-miss usernames do not authenticate. |
| Type | Negative |
| Priority | P3 - Medium |
| Design technique | Error Guessing |
| Requirements | IMP-1 |
| Tags | validation |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| Upper-case username | `Standard_User` |
| Username with spaces | `' standard_user ' (one leading and one trailing space)` |
| Password | `secret_sauce` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter 'Standard_User' in **Username**, 'secret_sauce' in **Password** and click **Login**. | The error 'Epic sadface: Username and password do not match any user in this service' is displayed and the URL remains https://www.saucedemo.com/. |
| 2 | Reload the page. Enter ' standard_user ' (with leading and trailing space) in **Username**, 'secret_sauce' in **Password** and click **Login**. | The error 'Epic sadface: Username and password do not match any user in this service' is displayed and the URL remains https://www.saucedemo.com/. |

### TC-1-014

**Allow login by pressing Enter in the Password field**

| Field | Value |
|---|---|
| Objective | Verify keyboard users can submit the form without clicking the Login button. |
| Type | Usability |
| Priority | P3 - Medium |
| Design technique | Use Case / Scenario |
| Requirements | IMP-2, AC-1 |
| Tags | keyboard |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| Username | `standard_user` |
| Password | `secret_sauce` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter 'standard_user' in **Username** and 'secret_sauce' in **Password**. | — |
| 2 | With focus in **Password**, press the Enter key. | The URL changes to https://www.saucedemo.com/inventory.html and the 'Products' header is displayed. |

### TC-1-015

**Allow successful login immediately after a failed attempt**

| Field | Value |
|---|---|
| Objective | Verify a failed attempt leaves no blocking state and the user can recover by correcting the credentials. |
| Type | Functional |
| Priority | P3 - Medium |
| Design technique | Error Guessing |
| Requirements | IMP-3, AC-1 |
| Tags | regression |

**Preconditions**

- Browser is on https://www.saucedemo.com/ with no active session.

**Test data**

| Name | Value |
|---|---|
| Wrong password | `wrong_password` |
| Correct password | `secret_sauce` |

**Steps**

| # | Action | Expected result |
|---|---|---|
| 1 | Enter 'standard_user' / 'wrong_password' and click **Login**. | The error 'Epic sadface: Username and password do not match any user in this service' is displayed. |
| 2 | Clear **Password**, enter 'secret_sauce' and click **Login**. | The URL changes to https://www.saucedemo.com/inventory.html, the 'Products' header is displayed and no error message is shown. |

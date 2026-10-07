# Test Design Techniques: When and How

Choose techniques from the **shape of the requirement**, not by habit. Most stories
need 2–4 techniques. Record the main technique on each test case.

## Contents
1. Technique selector
2. Equivalence Partitioning (EP)
3. Boundary Value Analysis (BVA)
4. Decision Table
5. State Transition
6. Use Case / Scenario
7. Error Guessing
8. Pairwise
9. Checklist-based (NFR)
10. Sizing guidance

---

## 1. Technique selector

| The requirement contains… | Apply |
|---|---|
| An input field, a range, or a format rule ("8–64 chars", "amount > 0", "valid email") | EP + BVA |
| Several conditions that combine into an outcome ("if premium **and** cart > $100 → free shipping") | Decision Table |
| A status, workflow, or lifecycle (Draft → Submitted → Approved) | State Transition |
| A user goal flowing across screens or systems | Use Case / Scenario |
| Anything users type, upload, or click | Error Guessing |
| Many independent configuration options (browser × OS × role × locale) | Pairwise |
| Accessibility, security, or performance expectations | Checklist |

---

## 2. Equivalence Partitioning

Split each input into classes that the system should treat the same way. Test **one
representative per class**, covering valid and invalid classes.

**Example:** "Quantity must be 1–99"
| Class | Representative | Expected |
|---|---|---|
| Valid 1–99 | 50 | Accepted |
| Invalid < 1 | 0 | Rejected |
| Invalid > 99 | 150 | Rejected |
| Invalid non-numeric | "abc" | Rejected |
| Invalid empty | "" | Required-field error |

You can combine several *valid* classes in one case. Test each *invalid* class in its
own case, so that one error does not hide another.

## 3. Boundary Value Analysis

Defects cluster at edges. For each ordered range, test the values **on** the boundary
and **just outside** it. This is 2-value BVA. Use 3-value BVA (also just inside) for
critical rules such as money or limits.

**Example:** "Password 8–64 characters" → test 7, 8, 64, 65.

Boundaries also exist in dates (end of month, leap day, timezone midnight), lists
(0, 1, max items, page size ± 1), files (max size, 0 bytes), and money
(0.00, 0.01, limit, limit + 0.01).

## 4. Decision Table

1. List the conditions, which are usually booleans.
2. List the actions and outcomes.
3. Enumerate the combinations (2^n). Collapse those whose outcome does not change
   ("don't care", `–`).
4. Each remaining column becomes one test case.

**Example:** Free shipping
| Rule | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| Premium member | Y | Y | N | N |
| Cart ≥ $100 | Y | N | Y | N |
| **Free shipping** | ✔ | ✘ | ✔ | ✘ |

Put the table in the test case's objective, or in the spec's scope summary, so
reviewers can check that it is complete.

## 5. State Transition

Model the states and events. Cover:
- **Every valid transition** at least once (0-switch coverage).
- **Invalid transitions**, such as approving a Draft or editing a Closed item. The
  expected result is rejection with no change of state.
- **Guards**, meaning conditions on a transition such as "only a manager can approve".

```
Draft --submit--> Submitted --approve--> Approved
                 Submitted --reject--> Draft
```

## 6. Use Case / Scenario

Write the **main success scenario** end to end, then one case for each **alternate**
and **exception** flow. These cases catch integration gaps that atomic cases miss, such
as an email actually being sent or a record appearing in another module. They are
usually P1 and tagged `smoke` or `e2e`.

## 7. Error Guessing

Use experience-driven probes that fit the context. Pick only the relevant ones:
- Empty, whitespace-only, leading or trailing spaces, very long strings
- Special characters, Unicode and emoji, RTL text, HTML or script injection (`<script>`), SQL metacharacters (`' OR 1=1 --`)
- Double-clicking submit, refreshing mid-flow, the browser back button after submit, two tabs open
- Session expiring mid-flow, loss of network, a slow dependency or timeout
- Concurrent edits by two users
- Changing an ID in the URL to reach another user's resource (IDOR)
- Copy-paste into masked fields, autofill
- Case sensitivity (emails, codes), duplicates

## 8. Pairwise

When there are several independent parameters, test every *pair* of values instead
of every combination. For example, 3 browsers × 3 OS × 2 roles = 18 combinations,
which a pairwise set covers in about 9. Use this only when the story is about
configuration or compatibility.

## 9. Checklist-based (non-functional)

**Accessibility (WCAG 2.2 AA)**, for new or changed UI:
keyboard-only operation and visible focus, screen-reader labels and announced errors,
colour contrast of at least 4.5:1, no information conveyed by colour alone, 200% zoom
with no loss of content.

**Security**, for authentication, permissions, PII, or payments:
authorization per role, IDOR, input sanitization, sensitive data masked in UI and logs,
session handling, rate limiting or lockout, no user enumeration in messages.

**Performance**, only with an explicit SLA or an obviously heavy operation:
response time under the stated load, behaviour with large data sets.

## 10. Sizing guidance

| Story complexity | Typical number of cases |
|---|---|
| Small (1–2 simple ACs, 1–3 points) | 5–10 |
| Medium (3–5 ACs, rules or validations) | 10–25 |
| Large (workflow, many rules, integrations) | 25–50, and suggest splitting the story |

Optimise for **requirement and risk coverage with minimal redundancy**, not for a
high count.

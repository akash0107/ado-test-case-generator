# Test Case Writing Standards

These standards are based on **ISO/IEC/IEEE 29119-3** (test documentation), the
**ISTQB Foundation** syllabus, and the field model of **Azure Test Plans**. Every test
case the skill produces must meet them. Run the review checklist at the end before
calling the work finished.

## Contents
1. Anatomy of a test case
2. Writing rules
3. Naming and IDs
4. Priority model
5. Test types
6. Test data rules
7. Anti-patterns
8. Review checklist

---

## 1. Anatomy of a test case

| Field | Purpose | Rules |
|---|---|---|
| **ID** | Unique, stable reference | `TC-<storyId>-NNN`, sequential, never reused |
| **Title** | What is verified, under which condition | ≤ 128 chars, pattern below |
| **Objective** | Why the test exists | One sentence on the behaviour or risk it guards |
| **Type** | Classification for reporting | One value from §5 |
| **Technique** | How the case was derived | See `test-design-techniques.md` |
| **Priority** | Execution order under time pressure | 1–4, see §4 |
| **Requirement refs** | Traceability | ≥ 1 requirement id (AC-n / REQ-n / NFR-n / IMP-n) |
| **Preconditions** | State that must exist *before* step 1 | Concrete and checkable: who is logged in, what data exists, which feature flag is on |
| **Test data** | Exact inputs | Named values, never "valid data" |
| **Steps** | Action → expected result pairs | See §2 |
| **Postconditions** | State left behind or cleanup needed | Only when relevant (e.g. "Delete test order #T-1001") |
| **Tags** | Filtering | e.g. `smoke`, `regression`, `api`, `mobile` |

## 2. Writing rules

1. **One objective per test case.** If the title needs "and", it is probably two cases.
   Exception: end-to-end scenario tests, where the objective *is* the flow.
2. **Steps are imperative and atomic.** "Enter `john@example.com` in the **Email** field."
   Not "Enter the details and submit".
3. **Expected results are observable and specific.** State what the tester will *see*:
   the exact message, value, state, redirect, record, or HTTP status. Never use
   "works", "correctly", "as expected", "properly", or "successfully" on its own.
4. **Not every step needs an expected result**, but every verification point does, and
   the **final step must have one**.
5. **Use the UI's exact labels** in **bold** (`**Save**`, `**Order history**`). If the
   story does not give the label, use a descriptive name and record an assumption.
6. **Self-contained.** A new tester with system access but no context must be able to
   run the case. No "same as TC-003" and no dependency on another case's leftovers.
   Put shared setup in preconditions.
7. **Deterministic.** The same data gives the same result. Avoid "any product"; name it.
8. **No implementation details** unless the story is technical (API or data). Test
   behaviour, not code.
9. **Keep it short.** Aim for 3–10 steps. More than 15 steps means the case should be split.
10. **Negative cases state the rejection behaviour**: message text, field highlight,
    no state change ("Order count remains 3"), no data persisted.

### Title pattern

`<Verify|Reject|Prevent|Display|Allow> <behaviour> <when/with condition>`

| Good | Poor |
|---|---|
| Verify reset link is emailed for a registered address | Forgot password test |
| Reject password shorter than 8 characters | Password validation |
| Prevent checkout when cart total exceeds credit limit | Checkout negative |
| Display empty-state message when user has no orders | Orders page |

## 3. Naming and IDs

- Test case: `TC-<storyId>-001`, `TC-<storyId>-002`, …, ordered by priority then flow.
- Requirements extracted from the story:
  - `AC-n`: an acceptance criterion, kept in the story's order.
  - `REQ-n`: a functional rule stated only in the description.
  - `NFR-n`: a non-functional requirement (performance, security, accessibility).
  - `IMP-n`: an implicit requirement that the story does not state but any reasonable
    user expects, such as validation, authorization, or error handling. Every IMP needs
    an entry in **assumptions**.

## 4. Priority model (Azure DevOps 1–4)

| Priority | Meaning | Typical cases |
|---|---|---|
| **1 – Critical** | Core happy path or a high-risk failure. A failure blocks release. | Main AC flow, security/authorization, data loss, payments |
| **2 – High** | Important rule or common negative path | Validation of required fields, key boundaries, main error handling |
| **3 – Medium** | Less frequent variations | Secondary boundaries, optional fields, UI states |
| **4 – Low** | Cosmetic or rare edge case | Layout, copy, unusual combinations |

Consider risk = **impact × likelihood**. Money, personal data, compliance, and
irreversible actions raise impact.

## 5. Test types

`Functional`, `Negative`, `Boundary`, `UI`, `Integration`, `Security`, `Accessibility`,
`Usability`, `Performance`, `Compatibility`, `Data Integrity`, `Regression`.

Include Security, Accessibility, and Performance cases only if the story touches them
(authentication, permissions, PII, forms and new UI, explicit SLAs). Scale them to the
story. Do not attach a generic security checklist to every story.

## 6. Test data rules

- Use realistic but **synthetic** data. Never use real customer PII, real card numbers,
  or production credentials. For cards, use processor test numbers (e.g. `4111 1111 1111 1111`).
- Boundary data must show the boundary value: `"7 chars: Abcd12!"`, `"8 chars: Abcd123!"`.
- When values depend on the environment (user accounts, IDs), name them as placeholders,
  `<registered_user_email>`, and say in the preconditions where to get them.
- Dates: give absolute values or relative rules ("today + 1 day"), with the timezone
  when it matters.

## 7. Anti-patterns

| Anti-pattern | Fix |
|---|---|
| "Verify the page works correctly" | Name the observable outcome |
| Steps that test several things at once | Split them, or make each verification its own step |
| Copying the AC text into a single step | Break it into actions with concrete data |
| Cases chained on one another's data | Move setup into preconditions |
| 40 near-identical cases for each input value | Use equivalence classes plus boundaries |
| Only happy paths | Add negatives, boundaries, and state/permission variations for every AC |
| Inventing behaviour that is not in the story | Record an assumption or open question instead |
| Expected result "Error is shown" | Quote the message, or describe the type and location of the error |

## 8. Review checklist (must pass before delivery)

**Coverage**
- [ ] Every requirement (AC/REQ/NFR/IMP) maps to at least one test case; the export script enforces this.
- [ ] Each AC has a positive case **and**, where input or state is involved, a negative or boundary case.
- [ ] Each business rule with several conditions is covered by a decision table.
- [ ] Each status or lifecycle field has its valid transitions and at least one invalid transition tested.
- [ ] Roles and permissions are covered where the story mentions users, roles, or ownership.
- [ ] Linked existing test cases were checked for duplicates.

**Quality**
- [ ] No vague expected results; the validator warns on these.
- [ ] Each case has concrete test data.
- [ ] Each case can be run on its own.
- [ ] Titles follow the pattern and are unique.
- [ ] Priorities are spread across levels; not everything is P1.

**Honesty**
- [ ] Every inferred behaviour appears in `assumptions`.
- [ ] Every ambiguity that changes an expected result appears in `open_questions`.
- [ ] Out-of-scope items are listed explicitly.

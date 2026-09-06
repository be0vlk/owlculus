# Evidence, notes, and Case export browser coverage

Ticket: [03 — Evidence, notes, and export integrity](../../../.scratch/key-flow-e2e/issues/03-evidence-notes-export-integrity.md).
Specification: [key investigation flows](../../../.scratch/key-flow-e2e/spec.md).

Implementation: `frontend/e2e/data-integrity.spec.js`, initially committed as `6469ba9` on `dev`.
All browser execution below uses Chromium, production gateway, `127.0.0.1`, desktop
1440×900, one worker, zero retries, and a fresh disposable stack per command.
The runner tears down only its project and volumes, including after failures.
Each test bootstraps independently with `beforeAll` and fresh authenticated API
fixtures; no execution providers or other journey credentials are required.

## Commands and results

Run from the repository root:

```bash
# G0: initial implementation verification
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
scripts/test-first-run-browser-journey.sh e2e/data-integrity.spec.js \
--workers=1 --retries=0

# G1: corrected fixtures and Entity locator
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
E2E_ARTIFACT_GROUP=integrity-final \
scripts/test-first-run-browser-journey.sh e2e/data-integrity.spec.js \
--workers=1 --retries=0

# G2: focused Case export verification after locator/report fixes
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
E2E_ARTIFACT_GROUP=integrity-exports \
scripts/test-first-run-browser-journey.sh e2e/data-integrity.spec.js \
--workers=1 --retries=0 --grep 'Case export'

# G3: standalone representative archive journey, schema-aligned assertions
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
E2E_ARTIFACT_GROUP=integrity-archive \
scripts/test-first-run-browser-journey.sh e2e/data-integrity.spec.js \
--workers=1 --retries=0 --grep 'Case export contains'

# S: focused support checks (from frontend/)
cd frontend
node --check e2e/data-integrity.spec.js
npx eslint e2e/data-integrity.spec.js
npx prettier --check e2e/data-integrity.spec.js
npx playwright test e2e/data-integrity.spec.js --project=chromium --list
npx vitest run src/views/__tests__/CaseDashboard.test.js \
src/components/entities/__tests__/EntityNotes.test.js
```

G0: 3 passed, 5 failed, 0 skipped, 0 expected failures. Two failures were product
defects; two were an ambiguous Entity Notes tab selector; one was a Task setup
permission error (Task creation requires Admin or Case lead). Ordinary Task setup
now uses the existing authenticated Admin API; the browser remains an Investigator.

G1: 5 passed, 3 failed, 0 skipped, 0 expected failures. The two product defects
remained. The third failure was an ambiguous Export button on the default Entities
tab; the Case archive scenario now opens Notes before using the Case Export action.
Both evidence tests continued beyond their soft failures to verify original bytes.

G2: 1 passed, 1 failed, 0 skipped, 0 expected failures. Export retry passed.
The archive test incorrectly expected API-added null Entity fields in the archive;
the archive stores supplied fields. Assertions now verify the seeded first name,
notes, Entity ID and Case ID without requiring unset optional properties.

G3: 1 passed, 0 failed, 0 skipped, 0 expected failures. The standalone journey
bootstrapped on a fresh stack and verified the complete representative archive.

Final per-scenario evidence across G1–G3: **6 passed, 2 failed, 0 skipped,
0 expected failures**. The two failures are separately filed product defects.
This is a testing-ticket completion report, not a claim that those two user
behaviors pass acceptance.

S: both focused Vitest files passed, 55 tests passed, 0 failed/skipped/expected
failures. Syntax and formatting checks passed. ESLint returned zero errors and
16 warnings about conditionals in the fixed Case/Entity and success/failure test
parameters. Playwright listed all eight independently selectable Chromium tests.
The frontend is JavaScript and has no frontend typecheck script; no backend Python
source changed, so unrelated backend mypy was not run. Production frontend builds
also passed during gateway stack startup. Archive inspection uses a uv-managed
Python environment and the standard ZIP reader (including CRC validation).

## Final scenario mapping

Append `--grep '<selector>'` to the group command to select a scenario on its own
fresh stack. The following selectors uniquely identify the eight tests:

| Selector | Evidence run | Acceptance result |
| --- | --- | --- |
| `organized Evidence` | G1 | Failed: stale folder path; identity, visible destination and downloaded bytes checked |
| `Case notes persist` | G1 | Passed: text and bold formatting after reopening; fresh authorized read |
| `Case notes retain` | G1 | Passed: visible save failure, retained formatted draft, unchanged server content, UI retry and reopening |
| `Entity notes persist` | G1 | Passed: formatted notes retained on intended Entity and Case |
| `Entity notes retain` | G1 | Passed: failed draft retention, unchanged server content, UI retry and reopening |
| `Evidence download reports` | G1 | Failed: no visible error; zero failed artifacts and byte-exact retry verified |
| `Case export reports` | G2 | Passed: visible error, no artifact, real retry ZIP with original Evidence bytes |
| `Case export contains` | G3 | Passed: metadata, notes, Entity, Task, folders/bytes and second-Case exclusion |

The representative archive journey checks Case metadata and Client ownership,
Case notes, Entity data/notes, Task data, Evidence manifest/folder organization,
and original file bytes. Distinct fixtures in a second Case must be absent from
all member names and decoded archive content. It does not freeze timestamps,
ZIP ordering, PDF layout, or require a Hunt.

## Product defects and artifacts

- [Stale Evidence folder path after move](../../../.scratch/key-flow-e2e-defects/issues/01-evidence-move-folder-path.md).
- [Missing Evidence download error feedback](../../../.scratch/key-flow-e2e-defects/issues/02-evidence-download-error-feedback.md).

These remain ordinary failing tests with meaningful assertions, not skipped or
expected-failure tests. A failed coverage scenario is not passing acceptance even
when later soft-assertion checks confirm bytes or retry behavior.

Artifacts live under `frontend/test-results/` (ignored local outputs):

- G0: `gateway-127.0.0.1-desktop/`
- G1: `gateway-127.0.0.1-desktop-integrity-final/`
- G2: `gateway-127.0.0.1-desktop-integrity-exports/`
- G3: `gateway-127.0.0.1-desktop-integrity-archive/`

Each root contains `stack.log`; failed tests contain `trace.zip`, screenshot and
`error-context.md`. Actual downloaded files/ZIPs are attached before inspection.
Archive inspection attaches `archive-members.json` with member names and base64
content, preserving inspection evidence without committing generated artifacts.
G1's organized Evidence folder contains `organized.txt`; the download failure
folder contains `retry.txt`, both verified against their original upload bytes.

## Inspected prior coverage (not executed here)

The first-run browser journey supplied upload, folder drag/drop and named control
patterns. Existing Case/session support supplied authenticated fixture patterns.
Backend `test_case_exports_api.py` and ExportService supplied current archive
schema semantics. These prior browser/backend suites were inspected, not rerun.
First-run checks and runner/frontend-server behavior remain unchanged, so no Vite,
extra viewport, full frontend/backend suite, or execution acceptance run was needed.

## Standards review

No hard documented violations. One judgement call: await the archive attachment
so reporting completion/errors are observed. Accepted and fixed. The reviewer
found no worthwhile duplication or abstraction changes.

## Spec review

No actionable missing requirements, scope creep, or wrong implementation found.
Reviewer explicitly required the two product defects remain failed acceptance.

Review findings: Standards 1 judgement call, fixed; Spec 0. No outstanding review
findings; both reviewers confirmed their follow-ups resolved. Runtime verification also corrected ambiguous Notes/Export selectors,
Task fixture authorization and aligned Case metadata assertions with the existing
export schema.

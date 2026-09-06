# Durable Plugin and Hunt browser coverage

Ticket: `.scratch/key-flow-e2e/issues/01-durable-plugin-hunt-execution.md`.
Specification: `.scratch/key-flow-e2e/spec.md`, stories 1–14 and 37–39.

## Scenarios

All scenarios are in `frontend/e2e/durable-executions.spec.js`. Each owns an
Investigator, two Clients/Cases and a unique provider marker. The group and any
individual `--grep` selection bootstrap on a fresh disposable stack.

| Scenario title | Contract verified |
| --- | --- |
| plugin survives navigation and reload with saving enabled | Same execution and retained output after reload; saved Evidence and Entity remain in original Case while the second Case is selected at completion |
| plugin survives navigation and reload with saving disabled | History and retained output survive reload; both Cases have no new Evidence or Entities |
| hunt survives navigation and reload with saving enabled | Hunt history/detail identity, completed step output and original Case effects after switching and reloading |
| plugin confirms cancellation and retains prior output | Output is persisted before visible cancellation; cancelled status and output survive reopening |
| hunt confirms cancellation and retains prior output | First step completes, second waits; confirmed cancellation preserves first output and prevents third provider invocation |
| plugin reopens failure information and partial results | Failed status, deterministic failure message and retained partial output in UI and authorized API |
| hunt reopens failure information and partial results | Required failing step yields Partial Success and retained step output, corroborated through API |
| plugin recovers lost acceptance once and permits an intentional repeat | Real accepted POST response is dropped; UI retry after reload recovers one identity, invocation and set of artifacts; deliberate repeat gets another identity |
| hunt recovers lost acceptance once and permits an intentional repeat | Same uncertain-acceptance and deliberate-repeat assertions through Hunt UI/history |

The Python startup overlay registers only a test provider, consistently across
the API, workers and provider children. The ordinary accepted definition/build
checks, dispatcher, broker, database, file storage and authorization stay real.
The launcher seeds only Hunt definitions. No production endpoints or execution
contracts changed. Test and launcher cleanup release barriers and remove only
the disposable stack's resources.

## Commands and results

All browser commands run from the repository root with Node 24 on PATH. Docker
and backend TestClient commands run outside the restricted sandbox. All browser
runs explicitly disable retries. The default browser is Chromium. Desktop is 1440×900; narrow is 390×844.

The execution support [README](README.md)
documents standalone selection and artifact locations.

Verification date: 2026-09-06. All nine new gateway scenarios passed, with zero
failures, skips or expected failures. No product defects have been identified; earlier failures
were test locator/orchestration errors, retained separately in the development
run ledger. The known Analyst client-list defect is outside these selections.

Use Node 24 for these commands (the verified local installation was
`/home/dragonborn/.nvm/versions/node/v24.20.0/bin`):

```bash
export PATH=/home/dragonborn/.nvm/versions/node/v24.20.0/bin:$PATH

# G: complete new gateway group
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
E2E_GATEWAY_PORT=18080 E2E_ARTIFACT_GROUP=execution-acceptance \
scripts/test-first-run-browser-journey.sh e2e/durable-executions.spec.js --workers=1 --retries=0

# V: independent single-scenario bootstrap; affected Vite/narrow variant
E2E_SERVER_KINDS=vite E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=narrow \
E2E_VITE_PORT=15173 E2E_ARTIFACT_GROUP=execution-variant-pass \
scripts/test-first-run-browser-journey.sh e2e/durable-executions.spec.js --workers=1 --retries=0 --grep 'hunt survives navigation'

# S: extracted helpers in existing invite and Task workflows, plus development checks
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
E2E_GATEWAY_PORT=18080 E2E_ARTIFACT_GROUP=executions-verified \
scripts/test-first-run-browser-journey.sh e2e/durable-executions.spec.js e2e/frontend-workflows.spec.js --workers=1 --retries=0 --grep 'survives navigation|hunt confirms cancellation|redeems an invite|persists a Task'

cd frontend
npx vitest run src/services/__tests__/executionSubmission.test.js
npx eslint e2e/durable-executions.spec.js e2e/execution-support/journey.js e2e/support/workflow.js e2e/frontend-workflows.spec.js
npx prettier --check e2e/durable-executions.spec.js e2e/execution-support/journey.js e2e/support/workflow.js e2e/frontend-workflows.spec.js
cd ../backend
UV_CACHE_DIR=/tmp/owlculus-uv-cache uv run --locked pytest tests/hunts/test_hunt_definition_check.py -q
UV_CACHE_DIR=/tmp/owlculus-uv-cache uv run --locked mypy app
UV_CACHE_DIR=/tmp/owlculus-uv-cache uv run --locked black --check ../frontend/e2e/execution-support/*.py
UV_CACHE_DIR=/tmp/owlculus-uv-cache uv run --locked ruff check ../frontend/e2e/execution-support
cd ..
bash -n scripts/test-first-run-browser-journey.sh
git diff --check
```

| Check | Pass | Fail | Skip | Expected failure | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| G: Chromium/gateway/127.0.0.1/desktop | 9 | 0 | 0 | 0 | `frontend/test-results/gateway-127.0.0.1-desktop-execution-acceptance/` |
| V: Chromium/Vite/127.0.0.1/narrow, Hunt completion only | 1 | 0 | 0 | 0 | `frontend/test-results/vite-127.0.0.1-narrow-execution-variant-pass/` |
| S: existing invite and Task selections | 2 | 0 | 0 | 0 | Same command also ran four new scenarios at an earlier revision (1 pass, 3 fail); see ledger |
| Submission service tests | 18 | 0 | 0 | 0 | Vitest focused file |
| Hunt definition validation | 10 | 0 | 0 | 0 | uv/pytest focused file; six existing dependency deprecation warnings |

Mypy passed for 117 source files. ESLint passed with zero errors and six warnings
about fixed Plugin/Hunt branches in parameterized tests. Prettier, Black, Ruff,
shell syntax and diff whitespace checks passed. There is no frontend TypeScript
check configured. The full frontend/backend/execution suites were not run.

## Development run ledger and failure artifacts

These earlier runs are **not** counted as final passing acceptance. All used
Chromium and `--workers=1 --retries=0`; none skipped or expected-failed a test.
Artifacts remain under `frontend/test-results/<directory>/`, including failing
screenshots, `error-context.md` and `trace.zip` in per-scenario subdirectories.
Later runner revisions also preserve `stack.log` and `provider-controls/`.

| Directory / command variation | Pass | Fail | What was corrected |
| --- | ---: | ---: | --- |
| `gateway-127.0.0.1-desktop`; G without artifact group and `--grep 'plugin survives navigation.*enabled'` | 1 | 0 | Initial saved Plugin smoke (host Node 22; final checks use Node 24) |
| `gateway-127.0.0.1-desktop-executions`; G with group `executions` | 4 | 5 | Scope cancellation status to the selected provider; include required-field asterisks in Hunt labels |
| `gateway-127.0.0.1-desktop-executions-final`; G with group `executions-final` | 4 | 5 | Use current Case dropdown interaction; open running Hunts in Active Executions; select intentional repeated Hunt by visible execution ID |
| `vite-127.0.0.1-narrow-execution-variant`; V with group `execution-variant` | 0 | 1 | Case dropdown is a select, not a search field |
| `vite-127.0.0.1-narrow-execution-variant-final`; V with group `execution-variant-final` | 0 | 1 | Use keyboard opening because custom selection content covers the input |
| `vite-127.0.0.1-narrow-execution-variant-verified`; V with group `execution-variant-verified` | 0 | 1 | Await completed overview navigation before reload |
| `gateway-127.0.0.1-desktop-executions-verified`; S exactly | 3 | 3 | Same navigation/reload synchronization; Hunt cancellation, existing invite and existing Task passed |

The assertions for retained data, identity, terminal state and Case effects were
kept intact throughout. Final gateway acceptance supersedes the development
failures. No production behavior was changed to make tests pass.

## Prior coverage inspected

These are inspection context, not newly executed acceptance results:

- Backend `tests/executions/runtime.py`, Plugin/Hunt execution system tests,
  cancellation, case effects and submission-dispatch tests supplied provider,
  readiness and persistence patterns. The full execution acceptance suite was
  not run.
- Frontend active-Case browser mocks and execution submission service tests
  supplied workflow/fault patterns; mocked browser success responses are not
  used by these new journeys.
- Existing first-run and real-backend frontend workflow journeys supplied named
  controls and authenticated bootstrap/fixture patterns.

## Review

The code-review skill reviewed the implementation against initial commit
`404737279d0ceec6da978d8915bf61052fa936bf` in independent Standards and Spec agents.

### Standards

No documented breaches or actionable judgment calls. The shared workflow
extraction removes duplication; test provider registration stays within the
disposable overlay. Plugin/Hunt branches reflect different UI/API contracts.

### Spec

No actionable findings. The nine scenarios cover lifecycle, optional saving,
cancellation, failures, Case ownership, uncertain acceptance and deliberate
repeats with persistent API corroboration.

A follow-up review of the navigation/active-Hunt delta also found no concerns.

Totals: Standards 0; Spec 0. There were no review judgment calls to apply.

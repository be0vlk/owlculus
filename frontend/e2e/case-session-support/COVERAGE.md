# Case/session isolation and Task handoff coverage

Ticket: [.scratch/key-flow-e2e/issues/02-case-session-isolation-task-handoff.md](../../../.scratch/key-flow-e2e/issues/02-case-session-isolation-task-handoff.md).
Spec: stories 1–2, 15–27, 37–39 in `.scratch/key-flow-e2e/spec.md`.

The group `frontend/e2e/case-session.spec.js` and any individual `--grep` selection
bootstrap their own disposable stack. Each scenario creates unique users,
Clients, Cases, notes and Tasks with authenticated product APIs. Browser login,
routing, stores, gateway, backend, database and authorization remain real.
The separate assignee uses a fresh browser context and its own login.

| Scenario (`--grep` text) | Contract |
| --- | --- |
| `switches real Case` | Visible switching and reloads preserve distinct notes and Tasks; fresh reads verify Case ownership |
| `late real notes` | Accepted original Case GET delayed until another Case's notes are visible |
| `late real Tasks` | Accepted original Task-list GET delayed until another Case's Tasks are visible |
| `accepted notes write` | Backend accepts original write before switching; delayed acknowledgement cannot change the new editor or write target |
| `assigned Analyst` | Assigned reading works; unrelated Case and Task API requests return 403; direct browser links expose no protected content and do not log out |
| `membership loss` | Admin removes open user's membership; next browser request rejects access and reconciles selection; late Task data cannot restore it |
| `expired signed credential` | Launcher signs an already expired token inside this stack; real backend returns 401; protected UI clears auth and Case context |
| `account change` | Same browser logs out/in; a previous-session response, Back and reload cannot restore former Case data |
| `Case lead assigns` | Lead creates and assigns through UI; separate Investigator discovers and completes; both reload and read the persisted result |

Only narrowly matched real-response delays are intercepted. They are released in
fixture teardown, including assertion failures. The launcher always records stack
logs and removes its uniquely named Compose project and volumes. No developer
records are deleted. Main-context traces/screenshots are retained on failure;
the second context is included in Playwright’s failure trace and saves `assignee.png`.

## Reproduction

From the repository root, with Docker and Node 24 available:

```bash
export PATH=/home/dragonborn/.nvm/versions/node/v24.20.0/bin:$PATH
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
E2E_GATEWAY_PORT=18080 E2E_ARTIFACT_GROUP=session-acceptance \
scripts/test-first-run-browser-journey.sh e2e/case-session.spec.js --workers=1 --retries=0
```

Append `--grep 'late real notes'` (or any table entry) for an independent scenario.
The runner automatically creates the expired credential when this file is selected.
It needs no execution-provider overlay. Set `E2E_SERVER_KINDS=vite`,
`E2E_VITE_PORT=15173` and optionally `E2E_VIEWPORTS=narrow` for existing variants.

Artifacts are under `frontend/test-results/<server>-127.0.0.1-<viewport>-<group>/`,
including `stack.log` and per-scenario failure artifacts. Use
`cd frontend && npx playwright show-trace <absolute-trace-path>` to inspect a trace.

## Verification ledger

Verification date: 2026-09-06. All nine new scenarios have passing gateway evidence:
eight in G, and the account-change scenario in its corrected focused rerun A.
The independent Vite/narrow scenario also passes. No new scenario is skipped or
marked expected-failure; no product defects were established.
The frontend has no configured typecheck command; JavaScript syntax, ESLint,
and the gateway's production Vite build provide applicable static checks.

Prior coverage inspected: `first-run.spec.js`, mocked `active-case.spec.js`,
`frontend-workflows.spec.js`, and session/active-Case integration tests. Inspection
alone is not counted as execution. The known Analyst client-list expected failure
(`.scratch/frontend-test-coverage-defects/issues/05-browser-analyst-clients.md`)
is distinct from passing authorized reading and route-denial assertions here.

Exact verification commands (same PATH as above):

```bash
# G: gateway group and separate existing Analyst checks
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
E2E_GATEWAY_PORT=18080 E2E_ARTIFACT_GROUP=session-acceptance \
scripts/test-first-run-browser-journey.sh e2e/case-session.spec.js \
e2e/frontend-workflows.spec.js --workers=1 --retries=0 \
--grep-invert 'redeems an invite|persists a Task edit'

# V: independent single-scenario bootstrap, affected Vite/narrow variant
E2E_SERVER_KINDS=vite E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=narrow \
E2E_VITE_PORT=15173 E2E_BACKEND_PORT=18001 E2E_GATEWAY_HTTPS_PORT=18444 \
E2E_ARTIFACT_GROUP=session-variant \
scripts/test-first-run-browser-journey.sh e2e/case-session.spec.js \
--workers=1 --retries=0 --grep 'expired signed credential'

# U: focused integration boundaries, from frontend/
npm run test:unit -- --run src/services/__tests__/session.integration.test.js \
src/router/__tests__/activeCase.test.js src/stores/__tests__/activeCase.test.js

# S: static checks, from frontend/
npx eslint e2e/case-session.spec.js e2e/support/case-session.js
npx prettier --check e2e/case-session.spec.js e2e/support/case-session.js
node --check e2e/case-session.spec.js
node --check e2e/support/case-session.js
bash -n ../scripts/test-first-run-browser-journey.sh
```

Development runs used the gateway command in Reproduction with
`E2E_ARTIFACT_GROUP=session-initial` and `session-corrected`, respectively.

| Run | Passed | Failed | Skipped | Expected failures | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Initial development | 1 | 8 | 0 | 0 | Test controls used outdated searchable-switcher names; membership recovery URL and select-pointer action also needed correction |
| Corrected development | 7 | 2 | 0 | 0 | Back-history expected destination and redundant manual tracing start needed correction |
| G | 9 | 1 | 0 | 1 | Eight new scenarios plus existing Analyst denial pass; account-change duplicate cell locator corrected in A |
| A | 1 | 0 | 0 | 0 | Account-change standalone rerun passes with unique Case-number cell |
| V | 1 | 0 | 0 | 0 | Expired credential on Vite/Chromium, 390×844 |
| U | 34 | 0 | 0 | 0 | Three focused files; no full suite |

Development artifacts are retained under the corresponding `session-initial`
and `session-corrected` directories. They are test implementation failures,
not established product defects or passing acceptance. Review subsequently
strengthened membership/account-change assertions to establish the replacement
Tasks workspace before releasing the delayed response.

## Review

Standards review: no documented-standard violations; two judgment calls accepted
and resolved. Held-response readiness now rejects with the original transport
error, and second-context cleanup survives screenshot failures.

Spec review: one coverage gap accepted and resolved. Membership loss and account
change now establish the replacement Case's Tasks before releasing the original
response, then assert those Tasks remain. This prevents a later fresh navigation
from hiding a stale-response overwrite. Both reviewers confirmed their findings
resolved in a focused follow-up.

The G runner prints “10 passed” because Playwright includes its expected-failure
result in that number. This report separates it: nine actual passes, one failure,
and one expected failure. The failure was an ambiguous test locator: Client name
and Case title intentionally matched, so two dashboard cells matched. A uses the
unique Case number and passes without altering the isolation assertion.

```bash
# A: final focused account-change verification, fresh gateway stack
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
E2E_GATEWAY_PORT=18080 E2E_ARTIFACT_GROUP=session-account-final \
scripts/test-first-run-browser-journey.sh e2e/case-session.spec.js \
--workers=1 --retries=0 --grep 'account change'
```

Final per-scenario evidence: all table scenarios except `account change` use G;
`account change` uses A; `expired signed credential` additionally uses V. All
production-gateway runs use Chromium, loopback, desktop 1440×900 and zero retries.
The original first-run and mocked active-Case browser files remain unchanged and
were inspected, not rerun. S passed without ESLint warnings; production frontend
builds completed during gateway setup. No backend code changed, no backend tests
were needed, and no full suite was run. Disposable stacks and temporary Vite probe
files were removed after both successful and failed runs.

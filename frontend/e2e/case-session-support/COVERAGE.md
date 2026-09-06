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
the second context saves `assignee-trace.zip` and `assignee.png`.

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

Verification date: 2026-09-06. Results are recorded after execution below.
The repository has no configured typecheck command; JavaScript syntax, ESLint,
and the gateway's production Vite build provide applicable static checks.

Prior coverage inspected: `first-run.spec.js`, mocked `active-case.spec.js`,
`frontend-workflows.spec.js`, and session/active-Case integration tests. Inspection
alone is not counted as execution. The known Analyst client-list expected failure
(`.scratch/frontend-test-coverage-defects/issues/05-browser-analyst-clients.md`)
is distinct from passing authorized reading and route-denial assertions here.

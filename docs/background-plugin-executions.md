# Background plugin and hunt executions

Standalone `POST /api/plugins/{name}/execute` now returns HTTP 202 JSON, not
NDJSON. Send the plugin parameters plus a positive `case_id` and optional boolean
`save_to_case` (default false). Validation and case authorization happen before
acceptance; provider calls happen only in the worker. An accepted response contains
`id`, `kind`, `case_id`, `status`, `created_at`, `dispatch_state`, `revision`, and
`links`. `Location` points to the detail resource.

- `GET /api/plugins/executions/{id}` returns durable state and structured errors.
- `GET /api/plugins/executions/{id}/results?cursor=0&limit=50` returns ordered
  original result events, a cursor for subsequent polling, and `next_cursor` when
  more retained results are available.
- `GET /api/plugins/executions/case/{case_id}?cursor=0&limit=50` returns newest-first
  case history. Pass `next_cursor` for older entries. Maximum page size is 200.

Queued and running work can be reopened from Plugins or the case dashboard.
Leaving the page releases polling resources; it does not cancel accepted work.
Failed work retains partial results. Empty output completes successfully. Saving
uses the initiating user's current case permissions and the original case.

## Hunt execution

`POST /api/hunts/{hunt_id}/execute` accepts `{case_id, parameters}` and returns
HTTP 202 with the existing execution fields plus `kind`, `dispatch_state`,
`revision`, observation `links`, and `Location`. The durable `pending` state is
shown as Queued. Detail (`?include_steps=true`), case history and PDF/JSON exports
keep their existing URLs and public execution/step IDs. Polling backs off from
one to ten seconds, stops at terminal outcomes, and is released on navigation.
Required step failures produce Partial with retained output; optional failures
can still complete. Execution-level errors are available in detail.

Hunts snapshot the accepted definition and a content hash of application Python
sources plus `uv.lock`. Deploy matching API and worker builds. An incompatible
worker fails queued work with `incompatible_build` before provider activity;
submit a new run after aligning builds. Each hunt uses one hunt worker slot and
calls the plugin runner directly for sequential steps. `HUNT_CONCURRENCY` defaults
to two prefork slots with prefetch one, independent of plugin capacity. Access is
rechecked at claim, before each step and at case-effect commits. Accepted case
and initiating user cannot change.

Upgrade 002 marks legacy pending/running API-owned hunts Failed with a
`legacy_interrupted` error and retained output; it never replays them. Historical
execution IDs, numeric step IDs and output are preserved. Duplicate historical
step labels receive `__legacy_duplicate_<id>` before enforcing unique associations;
all rows and outputs remain available in history and exports. New accepted work
has immutable definition/build snapshots. Stop old API processes before cutover.

## Upgrade and operation

Back up PostgreSQL and uploads before upgrading. Stop the API, dispatcher and
plugin and hunt workers during the upgrade; use a graceful worker shutdown to allow active
provider work to finish. Build the backend image and run:

```sh
docker compose run --rm db-init python -m app.database.upgrade_executions
docker compose up -d --build backend execution-dispatcher plugin-worker hunt-worker frontend
```

The explicit, versioned upgrade is transactional, repeatable, and adds immutable
submission/terminal-state guards. Existing hunt rows are preserved. Fresh installs
also apply the upgrade through db-init. Deploy the frontend and API together.

Development uses `docker compose -f docker-compose.yml -f docker-compose.dev.yml up
--build`, including the real dispatcher and worker. Restart workers after changing
plugin code. The worker uses the locked backend image, its own database pools and
event loop, ConfigurationApiKeyVault, and the same SECRET_KEY and uploads as the
API. Configure provider keys through Admin Configuration. Redis and PostgreSQL
remain on the private backend network; a worker egress network permits providers.

The plugin queue defaults to two prefork slots (`PLUGIN_CONCURRENCY`) and prefetch
one. See [Celery worker configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-prefetch-multiplier).
The dispatcher publishes database outbox entries and retries broker failures.
Its heartbeat health check measures successful database passes; workers use a
role-specific targeted ping. Ownership heartbeat is 10 seconds, lease 60 seconds.
Every result, terminal transition and case-effect commit checks that lease and
ownership generation. Provider calls do not hold database transactions.

Tickets 01–06 provide durable submission, bounded results and effects, cancellation,
and conservative worker recovery. A lost owner is fenced after its lease expires.
Only known-unstarted work and committed hunt boundaries can resume automatically.
Review retained output before deliberately rerunning an uncertain operation; a
rerun creates a new execution.

## Focused acceptance

From `backend`, run `RUN_EXECUTION_ACCEPTANCE=1 uv run --locked pytest
 tests/executions -q` outside the restricted TestClient sandbox. Docker must have
`postgres:15-alpine` and `redis:7-alpine` available. The reusable fixture starts
isolated containers with random loopback ports, committed PostgreSQL fixtures,
test-only worker-loadable providers, separate APIs, a dispatcher and a prefork
worker. Bounded readiness and process-group/container cleanup run even on failure.
It does not use eager Celery or live provider accounts.


## Reliable submission and dispatch

Both execution POST endpoints accept `Idempotency-Key` (1–200 characters), scoped
to the initiating user, execution kind and endpoint. A retry with the same
normalized case and payload returns the original execution, including after
completion, and rechecks current access. Retries use the accepted parameter
definitions, so later deactivation or changed defaults cannot hide acceptance.
Conflicting reuse returns 409. The
frontend persists unresolved keys in tab session storage across navigation and
reloads, scoped to the authenticated login, and reuses them when retrying the same
input. Storage contains only random keys and SHA-256 digests, never credentials or
investigation parameters. Restricted browser storage retains in-page retry support.
A submission after successful acceptance
gets a new key. Observation and reconnecting only read existing executions.

Admission is serialized in a short PostgreSQL transaction across API processes.
`EXECUTION_LIMIT_GLOBAL=1000`, `EXECUTION_LIMIT_CASE=100` and
`EXECUTION_LIMIT_USER=25` cap outstanding plugin and hunt executions together.
Configure identical limits on every API process; Compose forwards these values.
Terminal state releases capacity. Retrying accepted work consumes no extra slot.
Capacity rejection returns 429 with `Retry-After: 10`; database acceptance failure
returns 503. Neither creates partial accepted work or invokes a provider inline.

Upgrade `003_reliable_submission` adds durable submission identities with accepted
parameter definitions and dispatch
attempt timestamps/error metadata. Run the existing upgrade command before
starting the new API and dispatcher; it is safe to repeat on existing data.
Dispatcher claims use PostgreSQL row locks with `SKIP LOCKED`, held until publish
and acknowledgment commit. Multiple dispatchers can run concurrently. A crash
releases its locks, and redelivery retains the same Celery delivery ID. Workers
claim under the same control lock, preventing duplicate live provider starts.

Every `EXECUTION_REDISPATCH_SECONDS` (default 30 seconds), unstarted queued work
is eligible for republication even if its earlier publication was recorded.
This recovers from Redis queue loss independently of API traffic. Only executions
with no owner and generation zero are eligible; expired running owners are never
replayed here. Queued work can wait while workers are stopped. Status and the UI
show waiting reasons, acceptance time, last attempt and the next retry time.

Failed publications retry with exponential delays capped at 60 seconds plus up to
one second of jitter. Five consecutive failures produce immutable `dispatch_failed`
with guidance to restore services and deliberately submit a new run. A successful
publication resets the failure streak. Redis connect/read timeouts are two seconds;
Celery publication retries are disabled so PostgreSQL owns the retry policy.
No validation, authorization, credential or provider error is automatically retried.

## Bounded results and repeatable case effects

Workers enforce `EXECUTION_EVENT_LIMIT_BYTES` (1,048,576 by default) per compact
UTF-8 serialized ResultEvent, including its envelope, and
`EXECUTION_RESULT_LIMIT_BYTES` (26,214,400 by default) per standalone invocation or
hunt step. Both provider output and its redacted stored representation are checked. All
provider events count, including status/error events. These values
must be positive and should match across workers. A rejected event stops provider
iteration; it is never truncated or saved. A small runtime error/complete pair is
reserved outside the provider budget so reaching the limit still reports an
explicit `event_size_limit` or `result_size_limit` error and partial retained output.
Previously committed PostgreSQL chunks remain available, including when saving is
disabled or Redis live events expire. Required and optional hunt failures retain
their existing outcome semantics.

Hunt step events are available incrementally at
`GET /api/hunts/executions/{id}/steps/{step_id}/results?cursor=0&limit=50`.
Both plugin and hunt result pages default to 50 events and cap at 200. Existing
StepOutput, specialized renderers, and hunt exports retain their contracts. A
running/interrupted step's output is reconstructed from committed chunks when its
final output is unavailable. Failed/unfinished step output is explicitly labeled
partial. Evidence formatting remains intact; formatted documents larger than
2,097,152 characters are saved in ordered parts under the existing upload limit.

Upgrade `004_bounded_results_and_effects` adds hunt chunks, unique effect receipts,
result operation identities, and the shared cancellation-request boundary. Run the
existing repeatable upgrade command before starting updated API/workers. Case
context and initiating user remain fixed. Each evidence/entity operation uses a
stable execution + step + effect kind + ordinal identity. The receipt and existing
service mutations commit atomically; a retry after a lost acknowledgment skips the
committed effect. Different executions remain independent. A case row lock
serializes worker folder creation and entity matching/enrichment. Result/effect
transactions check current authorization, owner generation, lease and cancellation.

Execution evidence uses stable files in each case's `.execution-artifacts`
directory, with fsynced staging and atomic publication before the database commit.
Replaying an interrupted operation replaces its uncommitted artifact at the same
identity; it never creates a second visible evidence item. To remove abandoned
files from owners whose lease expired or whose execution terminated, run:

```bash
docker compose run --rm plugin-worker python -m app.executions.reconcile_artifacts
```

Reconciliation takes the writer's control lock, preserves database-referenced
files and live owners, and removes only recognized, unreferenced execution artifacts.
It leaves ordinary uploads, unrelated evidence, and unknown files alone. This is
file reconciliation only; provider replay and worker recovery remain separate
lifecycle responsibilities.

## Cancellation and deadlines

`DELETE /api/plugins/executions/{id}` returns the current execution. The existing
`DELETE /api/hunts/executions/{id}` now returns `status` alongside `execution_id`
and its message. Both require an active non-analyst with writable case access,
including retries and terminal records. Queued cancellation is atomic with claim;
running work becomes `cancelling`. Repeated requests preserve the current state.
Navigation only disconnects observation. Both views keep committed output and
poll until cleanup has been confirmed.

Each Celery slot supervises a separate Linux process session for its execution.
Blocking SDK calls, provider threads and command-line descendants belong to that
session. Cancellation checks PostgreSQL every half second independently of the
provider event loop; a best-effort Redis hint follows the durable request. The
supervisor sends TERM, allows up to four seconds for cooperative resource cleanup,
then kills and reaps remaining owned processes. It fences the owner and publishes
the terminal state only after cleanup. Normal completion also waits for cleanup.
Async subprocess streams drain stderr concurrently and retain at most 64 KiB of
error text. Cancellation does not signal other execution groups.

Configure `PLUGIN_EXECUTION_SECONDS` (900), `HUNT_STEP_SECONDS` (900), and
`HUNT_EXECUTION_SECONDS` (7200) consistently across execution services. Values must
exceed five seconds; each lifetime includes a five-second cleanup reservation.
Timeouts fail the execution with `execution_timeout`, preserve committed output,
and cancel unfinished hunt steps. Completed steps remain intact.

The supervisor renews ownership every ten seconds for a 60-second lease. Its
independent monotonic clock stops provider work before the last confirmed lease
expires even if a PostgreSQL call blocks. Database writes also reject expired or
superseded ownership. A control-storage outage delays the durable confirmation:
the view remains nonterminal until connectivity permits the cleanup report to
commit. Missing heartbeats alone do not mark an execution cancelled. Recovery waits
for cleanup confirmation or the enforced lease stopping bound plus five seconds.

Broker, result-backend transport, and Celery visibility settings use at least
10,800 seconds, increased automatically when the configured maximum execution
lifetime plus a 60-second margin is longer. Keep these lifetime values identical
across broker participants. Late acknowledgement and rejection on worker loss are
enabled together with database ownership and conservative reconciliation. A live
owner or terminal execution makes redelivery a no-op. Compose grants both worker
services a 75-second shutdown grace period.

Before starting updated workers and APIs, drain old workers and run the repeatable
`python -m app.database.upgrade_executions` upgrade. Version
`005_cancellation_deadlines` adds durable deadlines and provisional completion
state without changing retained results. Do not run old workers against the new
cancellation lifecycle. To roll back, stop and drain the updated workers first;
preserve the additive schema and all investigation records.

Focused distributed checks:

```bash
cd backend
RUN_EXECUTION_ACCEPTANCE=1 uv run pytest tests/executions/test_cancellation.py
```


## Worker recovery and hunt resumption

The dispatcher reconciles stale owners every ten seconds independently of API
requests and broker availability. Full batches of 100 are drained immediately,
committing between batches so a fleet outage does not wait another interval per batch. Ownership expires after the 60-second lease;
reconciliation observes an additional five-second cleanup margin. Detection and
recovery are bounded by 75 seconds after the last heartbeat plus dispatcher
scheduling tolerance. The provider process group has a database-free watchdog:
it receives monotonic lease/deadline updates over a pipe, and stops the group on
expiry or pipe EOF when its Celery supervisor is hard-killed. The control monitor
stops renewing ownership after losing its supervisor.

Each standalone invocation journals operation-start intent before calling the
plugin runner. Hunts journal intent atomically with step start, and clear it only
in the transaction committing the step's output and outcome. An interrupted
started operation without a committed outcome fails with
`interrupted_uncertain_outcome`; provider calls and case effects are never
silently repeated. Results, completed steps, and effect receipts remain readable.
Completion committed before broker acknowledgement stays terminal on redelivery.

A hunt at a committed boundary resumes its existing step records and reconstructs
HuntContext from committed StepOutput values, including failed optional/required
steps and dependency skips. Accepted definition snapshots and implementation build
identity remain authoritative. Incompatible builds fail with `incompatible_build`
before more provider activity. Current user activity and case access are checked
again at claim, later steps, and case-effect commits. Resumption preserves the
original execution start and deadline; it does not grant a fresh time budget.
Durably accepted cancellation takes precedence over recovery and completion.
Repeated failures before operation start have a separate five-attempt recovery
budget with capped exponential backoff and jitter. Exhaustion records
`recovery_exhausted` with instructions to check worker configuration and submit a
new run. A committed hunt step resets this consecutive-failure budget. Broker
publication retains its existing five-attempt dispatch policy.

Status and history expose `dispatch_state: recovery_waiting` with a readable
waiting reason while cleanup or safe redispatch is pending. Opening or refreshing
an execution only observes it. An uncertain failure requires an investigator to
review its retained output and deliberately submit a new execution to run again.

Upgrade with all previous API, dispatcher, and worker processes stopped. The
repeatable `006_worker_recovery` upgrade adds operation intent and recovery
metadata. Owned work from the previous schema is marked `legacy_unknown` so
missing intent cannot incorrectly authorize replay. Preserve the additive schema
and investigation records on rollback; do not mix old and new execution workers.

Focused recovery verification:

```bash
cd backend
RUN_EXECUTION_ACCEPTANCE=1 uv run pytest tests/executions/test_recovery.py
```

## Shared live observation (upgrade 007)

`POST /api/auth/websocket-token` accepts `{execution_id, kind}` (`kind` defaults
 to `hunt` for existing callers). The authenticated user must currently be active
and able to read the execution's case, including analyst readers. Tokens expire
in Redis after 30 seconds and are consumed atomically once. Kind and execution ID
are bound to the token; minting and consuming may use different API processes.

Open `/api/{plugins|hunts}/executions/{id}/stream?token=...`, optionally with
`cursor=<revision>-0` from an earlier stream. The first message is an authoritative
`snapshot`, or `resync` when the cursor is trimmed, expired, ahead of retained
history, or Redis has lost the stream. Both include current status, durable
revision, a cursor, and links to authorized execution detail and ordered results.
Load those result links to recover all output. Later `update` messages carry only
new revisions and result links; they are invalidations, not result bodies. A
snapshot supersedes earlier revisions, so clients need not replay old output.
The control-row lock makes the snapshot/revision consistent; independent Redis
XREAD cursors deliver newer retained updates to every API observer without a
consumer group. Legacy completed hunts without a control row remain readable.

Every revision journals an `ExecutionEvent` in the same PostgreSQL transaction as
its state or result change. The supervised dispatcher publishes committed intents
and removes each only after acknowledgment. Redis publication failures cannot
change execution status. Deterministic stream IDs make duplicate publication
safe. Upgrade 007 creates the journal and backfills the current revision for
existing controls; rerunning the upgrade is safe. Use the same stopped-process
upgrade procedure above before starting the new API, dispatcher and workers.

`EXECUTION_STREAM_LIMIT` defaults to 10,000 entries per execution (exact trimming).
`EXECUTION_STREAM_TTL_SECONDS` defaults to 86,400 seconds: active streams refresh,
and terminal retention is measured from durable completion, including delayed
publication. Cleanup removes no PostgreSQL history. Event keys use
`owlculus:events:<kind>:<id>`, token keys use `owlculus:tokens:<capability>`, separate
from execution queues, cancellation hints, and rate-limit state. Redis connections
have two-second connect and command timeouts. API observation buffers at most 100
small entries and has no application send queue. Each socket send has a two-second
deadline (`EXECUTION_STREAM_SEND_SECONDS`, capped at five); slow connections close
with code 1013 and a recoverable cursor. Current user/case authorization is refreshed
every five seconds (`EXECUTION_STREAM_AUTH_SECONDS`, capped at ten) and during
long batches; revoked observation closes with 1008.

Both frontends serialize durable reads, deduplicate results by cursor and state by
revision, and coalesce live bursts into refreshes. Failed streams reconnect with a
new token and their previous cursor while bounded polling backs off from one to ten
seconds. Terminal results drain any remaining pages and stop observation. Navigation
aborts reads and closes streams without cancellation or another submission. Hunt
step renderers and exports continue using their existing durable contracts.

Uvicorn handshake logging redacts observation token query values. Configure any
external reverse proxy or access-log collector to omit query strings for stream
URLs as well; capabilities and result bodies must never be logged.

Focused shared-observation acceptance: `RUN_EXECUTION_ACCEPTANCE=1 uv run --locked
pytest tests/executions/test_observation.py -q`. It uses real Redis 7, PostgreSQL,
independent APIs and workers; it includes deterministic snapshot and slow-transport
barriers, event loss/repair, authorization changes, and output above stream retention.

## Operations and release acceptance (ticket 08)

Run `docker compose exec backend python -m app.executions.operations` for a JSON
background capability report (exit 0 ready, 1 degraded). It reports pending and
active work by queue, unpublished dispatch backlog, oldest waiting age, dispatch
errors, live workers, retained failure/recovery totals, mean execution duration,
maximum completed cancellation latency, event publication backlog, and Redis
memory. A 30-second Redis dispatcher heartbeat identifies missing dispatch capability
and gates benchmark startup alongside worker readiness. Duration and cancellation aggregates cover retained history, not a rolling
window. Missing workers, failed dispatch, and waiting for capacity have distinct
conditions. Redis and worker inspection use bounded timeouts. `/health/live`
checks the API process; `/health/ready` checks API dependencies, independently of
worker availability. A healthy API can accept durable queued work while workers
are unavailable. Inspect dispatcher health separately with
`docker compose ps execution-dispatcher`.

`docker compose logs execution-dispatcher backend plugin-worker hunt-worker`
contains JSON dispatch records with execution ID, kind, attempt, generation, and
publication/retry state. `observation_failure` records identify stream reconnect
failures by kind, ID, and cursor; count these events over your chosen time window
using existing log tooling. Connection exceptions, credentials, tokens, and result
bodies are excluded. Investigation views retain their existing waiting reasons,
explicit errors, polling fallback, and durable result links.

Configuration defaults:

| Setting | Default / meaning |
| --- | --- |
| `EXECUTION_DISPATCH_POLL_SECONDS` | 0.2 seconds idle polling; minimum 0.05; recovery remains every 10 seconds |
| `PLUGIN_CONCURRENCY`, `HUNT_CONCURRENCY` | Two prefork slots independently; prefetch one |
| `PLUGIN_WORKER_MEMORY`, `HUNT_WORKER_MEMORY` | 1 GiB container limits each, including owned child processes |
| `WORKER_MAX_TASKS_PER_CHILD` | Recycle Celery children after 100 jobs |
| `WORKER_MAX_MEMORY_KB` | Recycle Celery children above 262144 KiB after their task; container limit bounds their subprocesses |
| `API_DATABASE_POOL_SIZE`, `API_DATABASE_MAX_OVERFLOW` | 5 + 5 connections in bundled API |
| `WORKER_DATABASE_POOL_SIZE`, `WORKER_DATABASE_MAX_OVERFLOW` | 2 + 0 per owning process |
| `PLUGIN_EXECUTION_SECONDS`, `HUNT_STEP_SECONDS`, `HUNT_EXECUTION_SECONDS` | 900 / 900 / 7200 seconds including cleanup |
| `EXECUTION_BROKER_URL`, `EXECUTION_EVENT_REDIS_URL` | Bundled Redis by default; direct launches fall back to `REDIS_URL` |
| `REDIS_MAXMEMORY` | 256 MiB, noeviction, AOF; Redis container 384 MiB |

Budget database connections for each API process plus each slot's supervisor,
control monitor, and execution process, plus the dispatcher and maintenance.
Pools are lazy and process local; with two slots per queue, a conservative worker
budget is 4 × 3 × 2 = 24 connections, plus dispatcher 2 and API 10. Allow room for
operations and migrations below PostgreSQL's connection limit. Pool acquisition
and PostgreSQL connection establishment time out after five seconds; execution
Redis connections use two seconds. The 60-second ownership lease still bounds
work if a database command becomes unresponsive. Workers receive 75 seconds for
shutdown; longer work is interrupted with retained output and conservative recovery.
Broker visibility is consistently at least three hours and automatically raised
above the largest plugin/hunt duration plus 60 seconds in all Celery settings.

Queues are `owlculus.plugins` and `owlculus.hunts`; events, control hints, tokens,
and rate limits have separate key namespaces. Namespaces and logical databases
provide no memory isolation. For stronger isolation, use physically separate
broker/event/rate-limit Redis services. Never use an eviction policy on a shared
broker: memory exhaustion must reject writes so durable outbox retry can recover.
Streams default to 10,000 entries and 24-hour retention; single-use tokens expire
after 30 seconds. Durable PostgreSQL results survive stream expiry. Provider
workers have the egress network; production PostgreSQL and Redis have no published
ports and stay on the private network. Development starts both queues and the
dispatcher, using the same source mount, secret, database, and uploads as the API.

### Upgrade and failed-rollout rehearsal

1. Stop new submissions (maintenance at the gateway), retain database and uploads
   backups, and record the current image digest. Check retained plugin results and
   a historical hunt JSON export before changing anything.
2. Stop the dispatcher to prevent further publication. Gracefully stop both old
   workers, allow the configured shutdown budget, and then stop the old API. Do not
   mix implementation builds. Queued hunts retain a definition snapshot and content
   build identity; a different build fails explicitly before provider work. Review
   those queued definitions and deliberately resubmit incompatible hunts after
   cutover; never rewrite an accepted build identity to force execution.
3. Run `docker compose run --rm db-init` with the new image. Initialization applies
   the explicit repeatable upgrade; it is not only table creation. Alternatively
   run `python -m app.database.upgrade_executions` in a configured backend container.
   Run it again to verify repeatability. Historical hunt and step IDs/output stay
   intact; API-owned nonterminal legacy hunts become `legacy_interrupted` failures.
4. Start compatible API, dispatcher, plugin-worker, and hunt-worker images. Check
   `/health/ready`, service health, and the operator report. Open retained results
   and export the historical hunt again. Run a deterministic plugin and two-step
   hunt before restoring submission traffic.
5. If rollout fails, stop new processes, keep the additive schema and all database,
   uploads, and Redis volumes, and deploy the last compatible image. Never use
   `down -v`, delete investigation rows, or replay uncertain provider operations.
   If the previous image cannot read the additive schema or accepted definitions,
   retain maintenance mode and roll forward with a corrected image. Restore a backup
   only through a separately reviewed recovery plan that accounts for newer writes.

The dedicated historical-schema test removes the new hunt columns and constraints
from populated records, upgrades twice, and verifies original IDs, outputs, history,
and exports through the API. The production-image fixture can rehearse API restart,
retained results, and compatible worker startup without outside provider accounts:

```bash
docker build --target production -t owlculus-execution-acceptance:ticket8 backend
cd backend
EXECUTION_TEST_IMAGE=owlculus-execution-acceptance:ticket8 RUN_EXECUTION_ACCEPTANCE=1 \
  uv run --locked pytest tests/executions/test_execution_system.py::test_provider_survives_api_restart_and_retains_ordered_partial_results \
  tests/executions/test_hunt_execution_system.py::test_hunt_survives_api_restart_and_uses_accepted_definition -q
```

This fixture runs the real locked image with separate API/dispatcher/prefork worker
containers and isolated PostgreSQL/Redis. It uses host networking only to reach
random loopback test ports; Compose topology checks separately verify production
privacy, egress, shared mounts, and matching configuration.

### Reproducible benchmark

Run on an otherwise idle reference host, outside restricted socket sandboxes:

```bash
cd backend
RUN_EXECUTION_ACCEPTANCE=1 RUN_EXECUTION_BENCHMARK=1 \
  EXECUTION_BENCHMARK_REPORT=/tmp/owlculus-benchmark.json \
  uv run --locked pytest tests/executions/test_performance.py -q
```

Timing begins after fault-free API and both worker queues are ready and the
dispatcher has started. Twenty submissions launch concurrently: ten five-second
plugins and ten two-step hunts, 2.5 seconds per step, with two slots per queue.
The report includes hardware, database defaults, output shape, submission/case-read
p95, queue wait, completion time, overlap, Redis memory, real rate-limit rejection
preservation, separate saturated-hunt plugin startup, and cooperative cancellation.
Targets are engineering acceptance criteria, not production SLAs. Run this test
separately from other workloads. It is opt-in and never part of ordinary unit runs.

The second opt-in test, `test_fault_and_limits_acceptance_under_load`, places
cooperative, blocking, subprocess, uncertain-owner and output-cap subjects ahead
of the same 20 concurrently submitted background jobs. It measures cancellation
while that work is outstanding, kills an actual prefork child and waits for natural
lease expiry (no timestamp editing), verifies conservative failure and retained
output, and proves results survive exact stream trimming and deletion. It uses
reduced 8-event/2048-byte limits to exercise bounds quickly. Set
`EXECUTION_FAULT_REPORT=/tmp/owlculus-faults.json` to retain its measurements.


### Reference measurements — 2026-09-05

Reference host: KVM Linux x86-64, four virtual AMD EPYC 9354P CPUs, 16,370,740 KiB
RAM. PostgreSQL 15 Alpine in an isolated Docker database with image defaults;
Redis 7 with AOF, 256 MiB maximum memory and noeviction. API pool 5+5, execution
pools 2+0; two prefork slots per queue, prefetch one. Processes run from the locked
uv environment. No external providers or billable requests. Results contain one
small JSON data object per provider and completion events; retained plugin result
and hunt detail responses totaled 22,567 bytes.

| Measurement | Observed | Target |
| --- | ---: | ---: |
| 20 concurrent submissions, p95 | 0.727 s | <1 s |
| Idle case read, p95 | 5.92 ms | Baseline |
| Case read under load, p95 | 16.51 ms | <500 ms here |
| All 20 jobs complete | 37.66 s | <40 s |
| Queue wait, p95 | 29.05 s | Recorded |
| Maximum concurrent executions | 2 plugins / 2 hunts | Exactly configured capacity |
| Idle plugin slot start while hunts saturated | 0.271 s | <2 s |
| Cooperative cancellation in saturation scenario | 1.224 s | <5 s |

Redis memory grew from 1,874,288 to 2,254,640 bytes
at the sampled peak. API/dispatcher/worker process-tree summed RSS peaked at
1,888,240 KiB; this sum includes shared
pages more than once, so it is not unique physical memory. A real bootstrap
rate-limit decision remained rejected after the execution workload, proving its
state survived. Operator report ended ready with zero pending/active work,
zero publication backlog, and live workers on both queues.

The initial one-second dispatcher idle poll missed the completion target on this
host: 40.35 seconds during concurrent verification, then 40.61 seconds in an
isolated run. Reducing only that poll to 200 ms produced the passing 37.66-second
reference measurement above. Provider durations and worker capacity stayed fixed.
These measurements describe this reference environment; they are not a production
SLA. Raw reports are retained in the local Redis issue directory as
`benchmark.json`, `benchmark-before-poll.json`, and `benchmark-contended.json`.

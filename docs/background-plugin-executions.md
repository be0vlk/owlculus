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

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

Tickets 01–03 provide plugin and hunt background execution with reliable submission
and dispatch. Output caps, cancellation and stale-worker recovery are delivered by
subsequent tickets. A lost running worker is fenced after its lease expires;
it is not automatically replayed in this slice. Do not delete execution records or
manually repeat uncertain provider work as a recovery mechanism.

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
completion, and rechecks current access. Conflicting reuse returns 409. The
frontend retains the key for uncertain responses across in-app navigation and
reuses it when retrying the same input. A submission after successful acceptance
gets a new key. Observation and reconnecting only read existing executions.

Admission is serialized in a short PostgreSQL transaction across API processes.
`EXECUTION_LIMIT_GLOBAL=1000`, `EXECUTION_LIMIT_CASE=100` and
`EXECUTION_LIMIT_USER=25` cap outstanding plugin and hunt executions together.
Configure identical limits on every API process; Compose forwards these values.
Terminal state releases capacity. Retrying accepted work consumes no extra slot.
Capacity rejection returns 429 with `Retry-After: 10`; database acceptance failure
returns 503. Neither creates partial accepted work or invokes a provider inline.

Upgrade `003_reliable_submission` adds durable submission identities and dispatch
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

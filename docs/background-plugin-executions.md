# Background plugin executions

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

## Upgrade and operation

Back up PostgreSQL and uploads before upgrading. Stop the API, dispatcher and
plugin worker during the upgrade; use a graceful worker shutdown to allow active
provider work to finish. Build the backend image and run:

```sh
docker compose run --rm db-init python -m app.database.upgrade_executions
docker compose up -d --build backend execution-dispatcher plugin-worker frontend
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

This is ticket 01: hunt execution migration, submission idempotency, dispatch
reconciliation, output caps, cancellation, and stale-worker recovery are delivered
by the subsequent tickets. A lost running worker is fenced after its lease expires;
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

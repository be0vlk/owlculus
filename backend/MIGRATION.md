# Upgrading an existing main installation

This procedure upgrades the PostgreSQL schema used by main at `3bc5348` to the
current application. It preserves the existing database and uploads. Use the
released code containing these changes; pulling main before the release will not
install the upgrades.

## Docker Compose cutover

Run these commands from the existing installation directory. Keep the same Compose
project name, `.env`, database credentials, and `SECRET_KEY`. Changing the project
name selects different named volumes; changing `SECRET_KEY` makes existing
encrypted provider keys unreadable. If you normally pass `-p`, `--env-file`, or
custom Compose files, retain those settings and adapt the commands accordingly.

1. Schedule downtime and let active Plugins and Hunts finish. Stop the old frontend
   and API before taking the backup. On an installation that already has background
   workers, gracefully stop its dispatcher and workers too.

   ```bash
   docker compose stop frontend backend
   ```

2. Back up PostgreSQL, uploads, configuration, and the old commit. Choose a new
   backup directory for each attempt and retain the old images for rollback.

   ```bash
   mkdir -m 700 migration-backup
   docker compose exec -T postgres sh -c \
     'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
     > migration-backup/database.dump
   docker compose cp backend:/app/uploads migration-backup/uploads
   cp .env migration-backup/.env
   cp docker-compose.yml migration-backup/docker-compose.yml
   git rev-parse HEAD > migration-backup/previous-commit.txt
   docker compose exec -T postgres pg_restore --list \
     < migration-backup/database.dump > migration-backup/database-contents.txt
   ```

   Confirm every command succeeds and retain any custom deployment files too.
   Rehearse restoration on a separate database before the production cutover.

3. Remove the old containers and networks, retaining volumes, then update and build
   the released code. Removing the old networks permits the new gateway network
   configuration to take effect.

   ```bash
   docker compose down
   git pull --ff-only origin main
   docker compose build
   ```

   Do **not** run `docker compose down -v`, `make clean`, or `setup.sh --clean`.
   These remove persistent data. Keep the existing `.env` instead of replacing it
   with example defaults. Review custom proxy configuration: browser API and
   WebSocket requests now go through the frontend gateway; backend port 8000 is
   no longer published. `DOMAIN` enables hostname matching and automatic HTTPS.

4. Run the combined initialization command from the new backend image:

   ```bash
   docker compose up -d postgres
   docker compose run --rm db-init
   ```

   Continue only after exit code 0. This invokes `python3 -m app.database.init_db`:
   table creation, account identity/session backfill, execution upgrades, invalid
   relationship cleanup, correlation provenance, and the default Personal client.
   Running only `upgrade_executions` does not apply the other upgrades.

   The component upgrades are transactional and repeatable; the entire command
   spans several transactions. If it fails, keep application processes stopped,
   correct the reported issue, and rerun the same command. Use one initialization
   process during cutover. Do not start old API or worker images on the upgraded
   database.

5. Start the complete updated stack, including Redis, both workers, and dispatcher:

   ```bash
   docker compose up -d
   docker compose ps -a
   docker compose logs --tail=100 db-init backend execution-dispatcher plugin-worker hunt-worker
   ```

   `db-init` should exit successfully; the backend, frontend, PostgreSQL, Redis,
   and workers should be healthy, and the dispatcher running. Sign in with an
   existing account, open an existing Case, download old Evidence, and run a new
   Plugin and Hunt that save results to the Case. Confirm configured provider keys
   still work. Existing installations skip first-administrator setup.

For rollback, stop the new stack, restore the pre-upgrade database and uploads,
restore the matching `.env` and deployment configuration, and run the old code and
images. There is no automatic downgrade migration; switching images alone does
not undo the authentication cutover or data cleanup. A backup restore discards
changes made after that backup.

## Changes visible to existing users

- Accounts, password hashes, Case memberships, Evidence paths/files/hashes, Entity
  data, Task history, templates, invitations, and stored configuration are retained.
  Everyone signs in again because legacy sessions are rejected.
- Historical Analyst lead flags are cleared. Evidence parents outside the Case or
  pointing at non-folders are detached; Task assignees without Case access are
  unassigned. Investigation records themselves are retained.
- Pending/running API-owned Hunts become failed with `legacy_interrupted`; their
  retained outputs remain available. Legacy step outputs without a verified
  dependency snapshot are restricted to Administrators, because their inherited
  Case scope cannot be established. Submit a new Hunt to run again.
- Duplicate historical step labels get a unique `__legacy_duplicate_<id>` suffix
  (with additional underscores if needed). IDs, outputs, and retry history stay
  intact. Upgrade `008_legacy_hunt_retries` supplies a database default for the
  retired `retry_count` column when present, permitting new steps after either a
  main upgrade or an earlier dev upgrade. Fresh databases need no retired column.
- Recognizable correlation reports lacking verified provenance become
  Administrator-only. Report bytes and hashes remain unchanged; regenerating a
  report establishes verified provenance.

## Regression coverage

`tests/fixtures/main_3bc5348_schema.sql` freezes all 13 tables, indexes, foreign keys,
and original nullability from the main models. It is independent of current ORM
metadata and does not require Git history at test runtime.
`tests/executions/test_main_upgrade.py` seeds every original table, runs the real
initialization entry point twice on disposable PostgreSQL 15, compares retained
records, and exercises login, Evidence download, encrypted provider-key use, and
new Plugin/Hunt work through API, Redis, dispatcher, and workers. It also verifies
reinitialization after new work, earlier execution upgrades, fresh schemas, and
colliding historical step labels.

Run the focused regression in the backend's locked environment:

```bash
RUN_EXECUTION_ACCEPTANCE=1 uv run --locked pytest tests/executions/test_main_upgrade.py -q
```

Docker and local process/socket access are required. This is a database/application
rehearsal, not a validation of an operator's custom proxy, images, or production data.

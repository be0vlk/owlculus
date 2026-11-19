# Upgrade to 2.1.1

If you're running an earlier version with Docker Compose, follow these steps.
Upgrading from 2.1.0 needs no database changes. Upgrading from 2.0.3 needs no
manual migration: `db-init` adds the new tables and columns. Steps marked *before 2.0.3* apply only to older installations. Schedule
downtime and run the commands from your existing installation directory.

Keep your Compose project name, `.env`, `POSTGRES_*` values, and `SECRET_KEY`.
Changing the project name selects different volumes; changing `SECRET_KEY` makes
stored provider keys unreadable. Use your usual `-p`, `--env-file`, and custom
Compose files with every command below.

1. **Stop application writes.** Let active Plugins and Hunts finish, then stop the
   frontend and API:

   ```bash
   docker compose stop frontend backend
   ```

   If your installation already has workers, also run:

   ```bash
   docker compose stop execution-dispatcher plugin-worker hunt-worker
   ```

2. **Back up before changing anything.** PostgreSQL must still be running. Use a
   new backup directory for each attempt (replace `migration-backup` if it exists).

   ```bash
   mkdir -m 700 migration-backup
   docker compose exec -T postgres sh -c \
     'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
     > migration-backup/database.dump
   docker compose cp backend:/app/uploads migration-backup/uploads
   cp .env docker-compose.yml migration-backup/
   git rev-parse HEAD > migration-backup/previous-commit.txt
   docker compose exec -T postgres pg_restore --list \
     < migration-backup/database.dump > migration-backup/database-contents.txt
   ```

   Stop if any command fails. Back up custom deployment files and retain the old
   images too. Verify the backup can be restored to a separate database.

3. **Update the code and configuration.** Remove containers and networks while
   retaining volumes:

   ```bash
   docker compose down
   git pull --ff-only origin main
   ```

   Never use `docker compose down -v`, `make clean`, or `setup.sh --clean` during
   this upgrade: they delete persistent data.

   *Before 2.0.3:* edit your existing `.env`; do not replace it with
   `.env.example`. If you do not already have a runtime database login, run `openssl rand -hex 32` and add:

   ```dotenv
   RUNTIME_POSTGRES_USER=owlculus_runtime
   RUNTIME_POSTGRES_PASSWORD=<paste the generated password>
   ```

   The runtime username must differ from `POSTGRES_USER`. If the runtime login
   already exists, keep its existing username and password. Initialization creates
   the new login automatically.

   *Before 2.0.3:* browser API and WebSocket traffic now goes through the frontend gateway;
   backend port 8000 is no longer published. Point any external proxy at the
   frontend. For Caddy-managed HTTPS, set `DOMAIN` to your public hostname and
   make ports 80 and 443 reachable; use `DOMAIN=:80` for HTTP.

4. **Build and migrate.**

   ```bash
   docker compose build
   docker compose up -d postgres
   docker compose run --rm db-init
   ```

   Continue only after `db-init` exits successfully. It applies all schema upgrades
   and provisions the runtime login. If it fails, keep the application stopped,
   fix the reported problem, and rerun `db-init`. It is repeatable; run only one
   instance at a time. Do not start old application images on the upgraded database.

5. **Start and verify.**

   ```bash
   docker compose up -d
   docker compose ps -a
   docker compose logs --tail=100 db-init backend execution-dispatcher plugin-worker hunt-worker
   ```

   `db-init` should show exit code 0; all other services should become healthy.
   Sign in with an existing account, open a Case, download old Evidence, and run
   a Plugin and Hunt that save results. Check that stored provider keys still work.

**Expected changes in 2.1.1:**

- If you provide `OPENAI_COMPATIBLE_API_KEY` through the environment, also set
  `OPENAI_COMPATIBLE_BASE_URL` to your server's base URL, and use the same URL
  under Admin > Strixy. The key is only sent to that URL. A key entered under
  Admin > Strixy is not affected.
- Investigators now see only the Cases they belong to when they view Clients.

**Expected changes in 2.1.0:**

- A `strixy` system user appears in the user list, named `strixy_ai_N` if
  `strixy` was taken. It is Strixy's identity; do not remove it.
- Strixy's default OpenAI model is now `gpt-6-astra`. Make sure your key can use
  it, or choose a provider and model under Admin > Strixy.
- Strixy runs in `plugin-worker` and shares `PLUGIN_CONCURRENCY` and
  `PLUGIN_WORKER_MEMORY` with Plugins; raise them for heavy use.
- Strixy can't read legacy `.doc` attachments.

**Expected changes from before 2.0.3:** Existing accounts and investigation data are retained, but
users with legacy sessions must sign in again. Invalid Evidence folder links and
Task assignments are cleared, as are historical Analyst lead flags. Unfinished
legacy Hunts are marked failed and must be resubmitted. Legacy Hunt outputs and
correlation reports without verifiable Case access may become Administrator-only;
rerun the Hunt or scan to generate new results.

**Rollback:** Stop the new stack, restore the pre-upgrade database, uploads, `.env`,
and deployment files, then run the saved old code and images. Switching images
alone does not undo migrations. Restoring the backup discards subsequent changes.

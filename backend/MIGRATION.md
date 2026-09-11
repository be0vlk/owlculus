# Upgrade to 2.0.3

If you're running a version earlier than 2.0.3 with Docker Compose, follow these
steps once 2.0.3 is released. Schedule downtime and run the commands from your
existing installation directory.

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

   Edit your existing `.env`; do not replace it with `.env.example`. If you do not
   already have a runtime database login, run `openssl rand -hex 32` and add:

   ```dotenv
   RUNTIME_POSTGRES_USER=owlculus_runtime
   RUNTIME_POSTGRES_PASSWORD=<paste the generated password>
   ```

   The runtime username must differ from `POSTGRES_USER`. If the runtime login
   already exists, keep its existing username and password. Initialization creates
   the new login automatically.

   Browser API and WebSocket traffic now goes through the frontend gateway;
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

**Expected changes:** Existing accounts and investigation data are retained, but
users with legacy sessions must sign in again. Invalid Evidence folder links and
Task assignments are cleared, as are historical Analyst lead flags. Unfinished
legacy Hunts are marked failed and must be resubmitted. Legacy Hunt outputs and
correlation reports without verifiable Case access may become Administrator-only;
rerun the Hunt or scan to generate new results.

**Rollback:** Stop the new stack, restore the pre-upgrade database, uploads, `.env`,
and deployment files, then run the saved old code and images. Switching images
alone does not undo migrations. Restoring the backup discards subsequent changes.

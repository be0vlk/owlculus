# Account authentication upgrade

Authorization ticket 01 replaces reusable usernames in authentication tokens with
permanent account UUIDs and persisted session versions. Password changes revoke
all existing sessions for the affected account. Users must sign in again after a
successful self-service change. Account IDs, password hashes, Case memberships,
Evidence files, and Task history are preserved by the upgrade.

For an existing PostgreSQL installation:

1. Back up PostgreSQL and the uploads volume using the normal deployment procedure.
2. Stop all API processes before the cutover. Drain accepted work, then stop workers
   and dispatchers while updating their application image. Do not serve authenticated
   requests from old API images during or after the database upgrade.
3. Using the new backend image and the existing database configuration, run
   `python3 -m app.database.init_db` (the Compose `db-init` service). This adds and
   backfills unique, non-null account identities and non-negative session versions,
   and clears historical Analyst lead flags. It does not recreate users or reset data.
4. Start all APIs, workers, and dispatchers with the new image and deploy the updated
   frontend. Require every user to sign in again.

Legacy bearer tokens and legacy Redis WebSocket capabilities are deliberately
rejected. There is no username or missing-version compatibility fallback. Old
WebSocket connections end when the old API processes stop. Newly issued capabilities
remain single use and expire after 30 seconds; password changes also revoke unused
capabilities and close open streams on their existing authorization recheck interval
(at most ten seconds). Accepted Plugin and Hunt work remains independent of browser
sessions, subject to the worker's current account, role, and Case access checks.

The account upgrade can also be run independently with
`python3 -m app.database.upgrade_authorization`. It is transactional, repeatable, and
serialized with other PostgreSQL initialization commands. It does not require
Ticket 02's relationship upgrade. Running it again preserves identities, credentials,
and session versions. Normal initialization composes the available upgrades.

Review baseline before remediation: 425 backend tests passed, with two existing
structural authorization assertion failures and one Redis mock argument-type
expectation failure; 35 frontend role tests passed. Verification for this change uses
focused account, Case policy, Task, frontend password-change, and disposable
PostgreSQL/Redis acceptance cases. The full suite is not a completion requirement.

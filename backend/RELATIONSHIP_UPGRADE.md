# Case relationship upgrade

Database initialization (`python -m app.database.init_db`) now detaches invalid
Evidence parent and Task assignee references. Deploy the corrected API alongside
this initialization step so older processes cannot create invalid relationships.
The cleanup is also independently runnable from the backend environment:

```bash
uv run --locked python -m app.database.upgrade_case_relationships
```

Run it with the deployment's database configuration. It is transactional and safe
to repeat. PostgreSQL uses the existing database-upgrade advisory lock. It needs
only the original relationship/account columns and can run before or after the
account lifecycle upgrade from authorization ticket 01.

The cleanup clears parents that are missing, are not folders, or belong to another
Case. It unassigns Tasks whose assignee is missing or cannot read the Task's Case.
Admin accounts remain eligible without membership; Analyst readers and inactive
Case members retain the existing assignment eligibility. Authentication still
controls whether an account can make requests.

No Cases, Evidence records, stored paths, physical files, Task history, or account
credentials are deleted or rewritten. A detached folder retains its existing
storage location. The API suppresses invalid historical relationship expansion
before cleanup, including Task assignees in Case exports.

Folder validation rejects invalid parent references before filesystem/database
changes, including for Admin callers. Unknown parents/users return 404, invalid
parents return generic validation errors, and ineligible assignees return 403.
Uploads retain their per-file failure response; bulk assignment retains its
best-effort list of successful Tasks. Null values in ordinary updates preserve
existing relationships; dedicated and bulk assignment still support unassignment.

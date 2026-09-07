# Correlation report access upgrade

Normal database initialization creates `correlationevidence` and runs the repeatable
backfill. Existing installations can run the same upgrade from the backend's locked
environment before starting the updated API and workers:

```bash
uv run --locked python -m app.database.upgrade_correlation
```

The upgrade preserves all report bytes, hashes, execution results, and receipts.
It records the source and related Case IDs only when an exact execution artifact
receipt and retained output establish them. Names recognize reports requiring
protection; they never establish permission. Recognizable legacy reports with
unverified provenance remain available only to Administrators. Regenerating the
report creates a new artifact with verified provenance.

New reports commit their Case provenance in the same transaction as Evidence and
its execution receipt. Ordinary Evidence updates cannot change that provenance.
Deleted Case IDs remain in the scope and deny non-Administrator access.

Retained Correlation Scan groups are projected for the current reader. Group
fields belong to the source Case; `matches[*].case_id` scopes each related match.
The allowlists in `executions/correlation_visibility.py` are the compatibility
contract for new fields. A notice outside these groups must carry a server-owned
`case_scope` list containing every Case represented by its content. Unknown or
unscoped summaries are omitted; errors use a fixed message. Later tickets must
extend these field scopes when adding match explanations and notices.

Hunt steps consuming a correlation output inherit its Case scope, including
transitive consumers and their saved reports. The accepted definition snapshot
identifies dependencies. If a legacy snapshot is unavailable, other steps are
conservatively treated as possible consumers. Unverified inherited scope permits
only Administrator reads. Independent steps with verified dependency definitions
retain ordinary behavior.

Plugin/Hunt reads, Evidence reads, and exports use `private, no-store` responses.
Browser correlation exports reload retained results before downloading. Filtering
preserves cursors based on inspected rows, including pages with no visible events.

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

Ticket 02 adds source `source_fields`, `normalized_value`, Case title/number, and
`executed_at` to each group. Related `fields` and `signal` remain inside the match
protected by its Case ID. Fields retain their original values; the normalized
value is the comparison key. Groups are identified by source Entity ID, kind,
and normalized value. `skipped_reference` data notices carry source and originating
Case IDs in `case_scope`, without the malformed value. Evidence and dependent Hunt
steps include notice scopes even when that Case contributes no match. Reports use
the recorded scan timestamp and count distinct source Entities separately from
matching reasons. Older retained payloads remain renderable without these fields.

Ticket 03 adds exact `email` and `phone` kinds. Email comparison trims surrounding
whitespace and normalizes the domain without changing local-part case, dots, or
plus tags. Phone comparison removes spaces, parentheses, dots, and hyphens; an
explicit `+` remains significant. Unsupported extension/free-text syntax produces
a scoped skipped-reference notice. Stored values are never rewritten.

Each related match now carries `signal_rank`: 0 for exact email/phone/VIN, 1 for
ordinary associations, and 2 for different email addresses sharing a common
provider (including groups with additional profile references). This is an ordering tier, not a probability.
Built-in providers are gmail.com, googlemail.com, outlook.com, hotmail.com,
live.com, yahoo.com, icloud.com, aol.com, proton.me, and protonmail.com. Explicit
Domain Entities and exact email matches at these providers are not downgraded.
The rank belongs to the related Case, just like the signal explanation. Clients
rank a group from its visible matches so hidden matches cannot affect prominence.
Ties use source Entity ID, kind, normalized value, related Case ID, and Entity ID.

New payloads carry `group_id` and `continuation: "merge"`. Every part is additive;
there is no numbered-part count, final-part marker, or related-derived group
metadata. The identifier hashes only source Case ID, source Entity ID, kind, and
normalized source value. Clients merge parts by this identity and deduplicate
related Entities by Case/Entity ID, retaining distinct field locations. A group
can recur later in the stream when it contains both ordinary and low-signal
matches. Legacy payloads without continuation metadata remain supported.
Cards, freshly authorized browser exports, and Evidence assemble the same groups.
Execution terminal state, rather than presence of a group part, establishes scan
completion. Hidden-only pages still advance the scanned-event cursor.

EntityCorrelation indexes normalized references with 256-Entity keyset fetches,
retaining only candidate references sought by source Entities. Detached values
survive worker read-transaction rollbacks without per-match ORM refreshes. The
Plugin streams one bounded part at a time rather than collecting every match;
its UTF-8 byte accounting includes the event envelope and repeated group metadata.
Scoped progress is emitted between bounded fetch/comparison portions. Cancellation
can run at progress and output boundaries. Per-event and per-operation limits
remain unchanged; an indivisible oversized match fails without truncation. On
failure, accepted output remains available as partial results, and no complete
Evidence report is saved. Reports saved after successful scans retain the existing
Case provenance, immutable bytes/hashes, and execution receipt protections.

Measured performance and reproduction commands: [correlation benchmark](CORRELATION_BENCHMARK.md).

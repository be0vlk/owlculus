# Correlation Scan ticket 03 benchmark

Measured on 2026-09-07 in the same local Linux/CPython 3.12 uv environment, with
isolated SQLite databases and tracing enabled for both versions. Each invocation
runs in a fresh process. The script creates schema-validated synthetic Entities;
no production data, network enrichment, or persistent index is involved.

| Workload | Version | Elapsed | First match | Peak traced memory | Process peak RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| 300 sources, 4,000 candidates, 60 matches | Before | 9.372 s | 9.366 s | 13.81 MiB | 106.82 MiB |
| Same sparse workload | After | 2.487 s | 2.458 s | 2.62 MiB | 81.78 MiB |
| 40 sources, 1,000 candidates, 40,000 shared-employer matches | Before | 4.190 s | 1.062 s | 9.10 MiB | 85.43 MiB |
| Same dense workload | After | 4.381 s | 0.665 s | 4.29 MiB | 73.89 MiB |

The sparse workload was about 3.8 times faster and used 81% less peak traced
memory. Dense total time was about 5% slower, while first-match latency improved
and peak traced memory fell 53%. Genuine matches still require proportional
work; this change primarily removes nonmatching pair comparisons and storage of
all expanded match pairs. These are measurements, not timing thresholds.

Both versions returned identical pre-existing-rule results, including source and
related identities, kind, normalized values, original field locations/values,
and qualification. The order-independent SHA-256 accumulators were:

- Sparse (60 matches): `cf78c8d0385f816f2ca5e360efb0397f9ed23c6812ecaf2d07d9103784e0e163`
- Dense (40,000 matches): `da53ab8169a1e266c25d5bd568242fc86bcf785b4cd88083af79f6b1f7835f38`

The benchmark isolates matching cost. It excludes seeding from timing, includes
fingerprinting in elapsed time, and does not measure PostgreSQL worker delivery
or Evidence formatting. Peak traced memory covers the measured matching phase;
process RSS also includes imports and seeding. Exact email/phone are excluded
from the legacy-result fingerprint. Access projection and durable output are
verified separately through focused public-boundary tests.

Reproduce from the repository root (then run the four uv commands sequentially):

```bash
git show 1baff7e:backend/app/services/entity_correlation.py > /tmp/correlation_ticket3_before.py
cd backend
uv run --locked python ../scripts/benchmark-correlation.py --baseline /tmp/correlation_ticket3_before.py
uv run --locked python ../scripts/benchmark-correlation.py
uv run --locked python ../scripts/benchmark-correlation.py --baseline /tmp/correlation_ticket3_before.py --dense
uv run --locked python ../scripts/benchmark-correlation.py --dense
```

The durable test uses a 2,400-byte event budget and 16 related Entities sharing
email/phone identifiers. A successful scan reopens across one-event pages and
saves one protected report with 49 reasons and one distinct source Entity. A
6,500-byte operation budget instead retains multiple email parts and fails
honestly before the group completes. Revoking related-Case membership removes
the retained matches and denies the original report download.

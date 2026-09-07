# Hunt correlation results

Hunt steps use the standalone correlation presentation after the backend applies current-reader access. Continuation portions assemble into logical groups; summary counts exclude skipped-reference notices and duplicate portions. Entity navigation, field explanations, legacy match kinds, and collapsed weak-provider sections use the same renderer. Collapse does not change exported or saved content. Hunt PDF correlation output retains all authorized rows; the existing generic Plugin PDF limit still applies to other Plugins.

Durable step status, partial execution output, and retrieval state are separate inputs. The adapter never synthesizes a successful completion event. Interrupted workers' retained chunks remain available with the failed step state and partial flag. Errors appear alongside the results.

`HuntResultReader` is created for one response, one execution, and one reader. Detail and export pass the already loaded steps into it. Context, step output, and step metadata share its Case-access assessment and dependency scope. `HuntCorrelationScope` memoizes each step's inherited scope and each correlation root's output validation for that lifetime. No object is saved on the session, worker, or user, and later requests reassess access. Unknown legacy dependencies still fail closed; the effect gate retains the same provenance rules.

## Bounded measurement

Measured on 2026-09-07 with the API fixture in `backend/tests/api/test_hunt_result_projection.py`, using SQLite, FastAPI TestClient, `time.perf_counter`, and `tracemalloc`. Each sample includes detail with steps plus JSON export, server-side serialization. The fixture has 25 steps, a 24-step consumer chain, 12 source groups containing 2,880 matches, and 4 KiB of actual derived output per consumer. Setup occurs outside the measured interval. These are single bounded observations, not production throughput predictions or timing assertions.

Baseline: `4abe3571d4cb961a8a238ed90cff993a58a1d4d0`.

| Reader | Before elapsed | After elapsed | Before peak | After peak |
| --- | ---: | ---: | ---: | ---: |
| Broad | 4.248 s | 0.465 s | 8.44 MiB | 8.39 MiB |
| Narrow | 4.214 s | 0.328 s | 6.03 MiB | 4.05 MiB |
| After membership revocation | 3.872 s | 0.234 s | 7.22 MiB | 4.97 MiB |

The visible step-output/context SHA-256 hashes were identical before and after:

- Broad: `3217c6e921c21e96a81185fd295c87611fa621af00124977f25ca176de80213d`
- Narrow: `b8b9200e8367208485f2e212d4ed807a7b57a4d0ca558c44b5b3e93a4feaed7b`
- Revoked: `b4196804c9dd9972548f12e971a893bcb5287f358552973ae27e9647273f0f1a`

The regression also compares detail/export content and checks visible match counts, hidden derived output, and revocation. Separate API tests cover unverified provenance, hidden-only pages, retained chunks after interruption, safe errors, and protected Evidence access.

The tradeoff is retaining small scope sets until response completion. Broad-reader peak memory is effectively unchanged because full response materialization dominates it. Complete correlation PDFs can grow larger than generic Plugin PDFs. No cross-request permission cache or timing threshold was introduced.

Reproduce the bounded measurement from `backend/` with `uv run pytest tests/api/test_hunt_result_projection.py -q --capture=tee-sys` outside the restricted sandbox.

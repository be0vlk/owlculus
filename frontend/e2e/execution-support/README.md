# Durable execution browser journeys

Run from the repository root with Node 24 and Docker available:

```bash
E2E_SERVER_KINDS=gateway E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop \
E2E_GATEWAY_PORT=18080 E2E_ARTIFACT_GROUP=executions \
scripts/test-first-run-browser-journey.sh e2e/durable-executions.spec.js --workers=1 --retries=0
```

Append `--grep 'hunt confirms cancellation'` (or any exact scenario title) to
bootstrap and run just that scenario on a fresh stack. `E2E_SERVER_KINDS=vite`
and `E2E_VIEWPORTS=narrow` select existing variants. The execution file activates
the test-only Compose overlay automatically; `E2E_EXECUTIONS=1` also enables it
when selecting tests using another Playwright pattern. Run the first-install
group on its own stack as before.

The overlay mounts `sitecustomize.py` into the API, dispatcher, workers and their
Python children. It adds a deterministic provider to the ordinary registry;
accepted-definition fingerprints, build compatibility, authentication, dispatch,
execution persistence and Case effects are untouched. `seed.py` inserts only
three Hunt definitions, which cannot be created through the public APIs. Each
scenario creates its own Investigator, Clients and Cases through those APIs.
No test definition is copied into production images.

Provider output is emitted before a bounded, file-backed release barrier. Each
scenario releases its own barrier in `finally`; launcher teardown also releases
all outstanding barriers before removing its containers, volumes and temporary
control directory. Readiness and provider invocation counts are test controls,
not simulated execution responses. Lost-response scenarios forward the real
POST and verify its 202 before aborting delivery to the browser.

Failed scenarios retain screenshots and traces. Runner output directories also
contain `stack.log` (frontend, API, dispatcher and workers) and
`provider-controls/`. Use a distinct `E2E_ARTIFACT_GROUP` to preserve results
across focused runs. Do not count an expected failure or skip as passing coverage.

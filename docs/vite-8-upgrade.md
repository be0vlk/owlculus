# Vite 8 upgrade verification

This maintenance upgrade moves from Vite 6.4.3 to the regularly patched Vite 8 line. The initial assessment did not establish an immediate Vue/Vuetify incompatibility. Version selection on 2026-09-06 checked the [Vite release policy](https://vite.dev/releases), [Vite 6 migration](https://v7.vite.dev/guide/migration), [Vite 7 migration](https://vite.dev/guide/migration), and npm package metadata.

## Resolved toolchain

| Package                        | Before | After  |
| ------------------------------ | ------ | ------ |
| Vite                           | 6.4.3  | 8.2.2  |
| `@vitejs/plugin-vue`           | 5.2.1  | 6.0.8  |
| `vite-plugin-vue-devtools`     | 7.6.8  | 8.2.1  |
| Vitest / `@vitest/coverage-v8` | 3.2.7  | 4.1.11 |
| `vite-plugin-vuetify`          | 2.1.3  | 2.1.3  |
| `@vitest/eslint-plugin`        | 1.1.10 | 1.1.10 |

Vite 8.2.2 was the latest stable Vite 8 patch in npm. Vitest 4.1.11 is a stable, Vite-8-compatible runner; choosing it avoids the additional Vitest 5 migration. Vue plugin 6.0.8 supports Vite 5–8 and Vue `^3.2.25`; DevTools 8.2.1 supports Vite 6–8; Vitest 4.1.11 supports Vite 6–8 and its coverage provider requires exactly that runner version. Vuetify's existing plugin supports Vite `>=5`, Vue `^3.0.0`, and Vuetify `>=3`; the existing Vitest lint plugin accepts any Vitest version. `npm ls` resolves all these consumers to one Vite 8.2.2 without invalid peers.

Verification uses Node 24.20.0 and npm 11.19.0 from the installed Node 24 runtime. Engine enforcement, `.nvmrc`, and `packageManager` remain unchanged, as do all direct application dependencies, including Vue 3.5.42, Vuetify 4.2.0, and Tiptap 3.31.3.

The initial combined npm update encountered the old tightly coupled Vitest/coverage entries. Removing that pair from the manifest and resolving the lock, then adding the new matching pair and resolving again, allowed ordinary npm resolution. A subsequent `npm ci` installed successfully with zero reported vulnerabilities. No force flags, legacy peer resolution, package aliases, or overrides were used. The lockfile retains its existing two-space formatting.

## Configuration decisions

- Removed the unsupported object-form `manualChunks.auth` setting and its empty build wrapper. Its comment described HMR, but this was a production-only option. Automatic Rolldown splitting preserves the application's static auth imports and dynamic route imports without imposing a manual group. [Rolldown manual splitting](https://rolldown.rs/in-depth/manual-code-splitting) can recursively capture dependencies and introduce chunk cycles; no measured requirement justifies recreating the group.
- Retained the application alias, runtime-compiler Vue alias, Vuetify auto-imports, and full explicit Vuetify optimizer list. The browser journey checks first route visits and retains a document marker across HMR and client navigation to detect full reloads.
- Retained host binding, disabled CORS, proxy headers, WebSocket forwarding, backend target override, and HMR overlay preference. Existing configuration tests protect these settings.
- Retained Vitest's merged application configuration, jsdom, aliases, and inline Vuetify dependency handling. Added explicit extensions to configuration imports to resolve Vite 8's native-loader compatibility warning.
- Removed Vitest's obsolete `coverage.all`; the existing explicit include list continues collecting uncovered sources. Coverage mapping required the measured recalibration below.
- No browser support policy was found in the repository. Vite 6's default targeted Chrome 87, Edge 88, Firefox 78, and Safari 14. Vite 7 moved to 107/107/104/16.0; Vite 8 defaults to Chrome 111, Edge 111, Firefox 114, and Safari 16.4. The build adopts this Vite 8 baseline; no legacy framework or explicit older target was added. Vite 8 also changes CSS minification to Lightning CSS.

## Focused checks

Run from `frontend` with Node 24/npm 11:

```bash
npm ci
npm ls vite @vitejs/plugin-vue vite-plugin-vue-devtools vite-plugin-vuetify vitest @vitest/coverage-v8 @vitest/eslint-plugin vue vuetify
npm run build
npm run test:unit -- --run src/services/__tests__/viteServer.test.js src/services/__tests__/runtimeBaseline.test.js src/__tests__/App.test.js src/stores/__tests__/auth.test.js src/components/__tests__/Vuetify4PublicSeams.test.js src/components/__tests__/NoteCompatibility.test.js
npm run test:coverage:audit
```

The six requested files pass all 65 tests, covering Node configuration loading, runtime metadata, authentication loading/store behavior, public Vuetify contracts, and real Tiptap editing. The eight-file audit passes 109 intended cases and retains 15 expected failures. No application unit-test assertions or mocks required migration. The frontend has no typecheck script; the repository's `make typecheck` checks only the unchanged backend. Focused ESLint, Prettier, and the production build provide applicable frontend checks.

### Coverage comparison

An isolated `git archive` of starting commit `7cb37e2`, installed from its original lockfile under the same Node/npm runtime, reproduces every original audit floor. The upgraded toolchain measures the identical 28 source files with the identical eight suites and 124 cases. There are no added or removed collected files. [Vitest 4's migration guide](https://v4.vitest.dev/guide/migration) explains its AST-based V8 remapping and changed handling of non-runtime lines.

| Metric     | Original toolchain   | Upgraded toolchain   |
| ---------- | -------------------- | -------------------- |
| Lines      | 4135 / 5012 (82.50%) | 1316 / 1979 (66.49%) |
| Statements | 4135 / 5012 (82.50%) | 1395 / 2144 (65.06%) |
| Functions  | 155 / 344 (45.05%)   | 454 / 754 (60.21%)   |
| Branches   | 571 / 731 (78.11%)   | 799 / 1315 (60.76%)  |

The previous numerical floors are incompatible with the changed measurement. The baseline now enforces every newly measured total and per-file metric, including increases, without changing collection scope, tests, or expected failures. The baseline metadata preserves the original totals and links to this comparison. This is a one-time explicit recalibration, not automatic threshold updating. Existing uncovered behavior and expected failures remain provisional, as described in [the audit report](../frontend/TEST_COVERAGE.md).

## Browser and container checks

From the repository root:

```bash
E2E_SERVER_KINDS='vite gateway' E2E_HOSTS=127.0.0.1 E2E_VIEWPORTS=desktop E2E_GATEWAY_PORT=18080 ./scripts/test-first-run-browser-journey.sh e2e/first-run.spec.js
```

The runner already accepts focused file selection and server/host/viewport controls, so no runner changes are needed. Each mode builds a fresh frontend image and creates an ephemeral backend/database stack. Development starts with a fresh container dependency volume and optimizer state; production uses the existing Node 24 Alpine builder and Caddy image. The three serial cases cover neutral startup, first administrator setup and login, and authenticated workflows.

Both complete journeys passed on 2026-09-06 with Chromium, `127.0.0.1`, and the desktop viewport: development **3/3** (49.6 s), production gateway **3/3** (38.4 s). Each passed setup, subsequent login, authenticated startup and refresh, Case/Entity editing and notes, Evidence dialogs/uploads, Task creation/assignment, Hunt controls, administration, retained Plugin results, and Settings. Development additionally passed module and Vue template HMR, restoration, and document continuity across first lazy-route visits. The existing runtime observer found no unexpected browser exceptions, console errors, failed requests, cross-origin traffic, or CORS preflights, and observed the development HMR WebSocket handshake and updates.

The fresh Alpine image completed `npm ci`, Vite's production build, and both existing Caddy configuration validations. Chromium consumed those built assets through Caddy on port 18080. All disposable containers and volumes were removed; the temporary HMR module was removed and `App.vue` restored byte-for-byte.

Screenshots were inspected for Clients in both themes in both modes, Evidence folder dialogs and dark Case notes in both modes, and development Tasks and Plugin results. No missing icons, unstyled dialogs, or clipped controls were observed on those surfaces. This was a representative visual check, not a pixel-diff or additional browser-support certification. Local screenshots and stack logs are under `frontend/test-results/{vite,gateway}-127.0.0.1-desktop/`. No additional hosts, viewports, or browsers were needed.

Vue DevTools was separately opened in Chromium on a temporary local Vite server with an application page connected. Its component inspector rendered `App`, `VApp`, `RouterView`, and the snackbars, and exposed the App's reactive auth/active-Case state. The temporary server was stopped after inspection.

The journey now checks both a real module edit and a temporary rendered Vue template edit, restores the original component in `finally`, checks document continuity across route visits, and explicitly reloads the authenticated Plugin route. The two Vue edits are separated by 150 ms because the file watcher throttles rapid successive changes; otherwise the restoration event can be coalesced. A pre-existing Case title locator was scoped to the main content after the active-Case header introduced a second identical title. The existing durable Plugin workflow requires waiting for completion and opening “View retained results”; the journey now takes those steps before checking the result dialog, export control, and correlation output. The parameter panel is now asserted absent for Correlation Scan: the existing execution service removes `case_id` and `save_to_case` from normalized Plugin parameters, leaving an empty object. This updates an obsolete display assertion to the current contract. No product code changed for these harness corrections.

## Warnings and scope

Both the original build and the upgrade warn about a statically and dynamically imported `GenericPluginParams.vue` and chunks over 500 kB. The original additionally reports similar mixed imports for other Plugin helpers. The new build succeeds without unresolved imports; these existing warnings were not suppressed or addressed through speculative application changes.

Clean npm installation warns that unchanged ESLint 9.39.5 is unsupported and reports undeclared install-script approval for the existing `@parcel/watcher` and `vue-demi` packages. Native installation and build are verified separately; no unrelated package updates or script policy changes were made. No full frontend, backend, or repository suite, deployment, or backend implementation change is part of this migration.

Independent standards and specification reviews compared the changes with starting commit `7cb37e2` and returned zero actionable findings. They also checked that every original and recalibrated coverage floor matches its corresponding measured report.

## Maintenance resolution — 2026-09-06

The two installation warnings recorded above are now resolved by the [frontend dependency maintenance](frontend-dependency-maintenance.md): supported ESLint 10.10.0 with compatible Vue parsing and utility peers, and explicit exact-version approvals for `vue-demi@0.14.10` and `@parcel/watcher@2.5.1`. Clean local and fresh Node 24 Alpine installs pass with strict project policy and without either targeted warning. Lint preserves the 22 existing Playwright warnings; focused tests, Vue 3 compatibility, native watcher edits, Sass compilation, and production builds pass. The historical Vite verification and resolved Vite issue remain unchanged.

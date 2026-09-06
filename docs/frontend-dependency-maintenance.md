# Frontend dependency maintenance — 2026-09-06

Resolves the ESLint support and undeclared lifecycle-script warnings recorded by the [Vite 8 migration](vite-8-upgrade.md). Starting commit: `a1da9b104f6986f22c62b5e7dd8f981771872c75`. The scope is the [combined maintenance ticket](../.scratch/frontend-dependency-maintenance/issues/01-resolve-frontend-dependency-maintenance-warnings.md).

## Version and peer review

The [official support table](https://eslint.org/version-support/) identifies ESLint 10 as current and ESLint 9 as EOL since 2026-08-06. Registry metadata (`npm view <package> version peerDependencies engines --json`) was checked on the date above; ESLint 10.10.0 and core config 10.0.1 were stable latest releases. The [ESLint 10 migration guide](https://eslint.org/docs/latest/use/migrate-to-10.0.0) calls out changed recommended rules, file-relative config discovery, and removed plugin APIs. Node 24 satisfies its engine requirement.

| Integration | Resolved version | Compatibility finding |
| --- | --- | --- |
| `eslint` | 9.39.5 → 10.10.0 | Node `^20.19.0 \|\| ^22.13.0 \|\| >=24` |
| `@eslint/js` | 9.39.5 → 10.0.1 | ESLint `^10.0.0` |
| `eslint-plugin-vue` | 9.33.0 → 10.10.0 | ESLint 8.57/9/10; parser `^10.3.0` |
| `vue-eslint-parser` | 9.4.3 → 10.4.1 | ESLint 8.57/9/10; shared with Vuetify |
| `@vitest/eslint-plugin` | 1.1.10 retained | ESLint `>=8.57.0`, Vitest `*`, utils `>=8.0` |
| `@typescript-eslint/utils` | 8.18.0 → 8.69.0 | Required peer update: old version excludes ESLint 10; new version accepts 8.57/9/10 and TypeScript `>=4.8.4 <6.1.0` |
| `eslint-plugin-vuetify` | 2.7.2 retained | ESLint 8/9/10, Vuetify 3/4 |
| `eslint-plugin-playwright` | 2.1.0 retained | ESLint `>=8.40.0`; actual rules exercised successfully |
| `@vue/eslint-config-prettier` | 10.1.0 retained | ESLint `>=8.21.0`, Prettier `>=3` |
| `eslint-config-prettier` | 9.1.0 retained | ESLint `>=7` |
| `eslint-plugin-prettier` | 5.2.1 retained, not enabled | ESLint `>=8`, Prettier `>=3` |
| `prettier` | 3.4.2 retained | Formatting stays separate from lint |
| `globals` | 13.24.0, now direct | Same browser definitions formerly supplied by Vue plugin 9 |

Vue plugin 10.10.0 was already resolved under Vuetify and supports ESLint 10, so it was reused instead of taking the newly available 10.11.0. The existing Vitest plugin's supported utility peer was updated without upgrading the plugin or runner. No other direct dependency was upgraded. Vue 3.5.42, Vuetify 4.2.0, Pinia 2.3.0, Sass 1.89.1, Vite 8.2.2, Vitest/coverage 4.1.11, and Tiptap 3.31.3 remain unchanged. ESLint and utility transitive dependencies changed as required by ordinary resolution.

Initial simultaneous installs hit npm's existing coupled Vue/parser entries. After updating the utils peer, temporarily removing the three direct lint entries, resolving, and restoring the final manifest allowed normal resolution. No force, legacy peer resolution, aliases, or overrides were used. The final manifest and lock install together, and `npm ls --all` exits zero locally and in both Alpine build environments. The lock retains its two-space indentation.

## Configuration and lint comparison

[Vue plugin 10](https://github.com/vuejs/eslint-plugin-vue/releases/tag/v10.0.0) removes implicit browser globals. The configuration now imports the same `globals.browser` definitions explicitly. File matching (`js`, `mjs`, `jsx`, `vue`), generated `dist`/`dist-ssr`/`coverage` exclusions, `localStorage`/`window`, Vue parsing, Vuetify's v4 recommendation, Vitest's `src/**/__tests__/*` scope, Playwright's journey scope, and the final skip-formatting configuration remain intact. Existing flat-config APIs load under ESLint 10 without an API rewrite or compatibility shim. No plugin or rule was disabled.

Before changes, non-fixing `eslint . --format json` scanned 265 files: **0 errors, 22 warnings**. After changes it scans 267 files (including two new verification files): **0 errors, the identical 22 warnings**. Comparison included path, rule, severity, line, column, and message. The existing warnings are entirely in Playwright journeys:

| File | `playwright/no-conditional-in-test` lines | `playwright/no-conditional-expect` lines |
| --- | --- | --- |
| `e2e/data-integrity.spec.js` | 130, 137, 155, 167, 174, 198, 212, 235 | 175, 176, 177, 178, 180, 198, 237, 243 |
| `e2e/durable-executions.spec.js` | 12, 86, 127 | 88, 89, 90 |

The initial upgraded pass exposed 383 missing-browser-global errors and four new core diagnostics. Explicit globals resolve the former. `no-useless-assignment` is resolved by initializing the password-strength score once after its checks; behavior is unchanged. `preserve-caught-error` is resolved by attaching `cause` to the three API-key mutation errors, preserving their existing display messages and pending-state cleanup.

[The repeatable maintenance smoke check](../frontend/scripts/verify-dependency-maintenance.mjs) uses invalid in-memory examples to provoke core, Vue, Vuetify legacy-prop and v4 typography, Vitest assertion, and Playwright timeout diagnostics. It checks extension matching, test-rule exclusion from application code, output ignores, browser globals, and acceptance of formatting differences. The JSX-extension probe checks file selection with ordinary JavaScript; this change does not introduce JSX compilation. Full non-fixing lint also covers all real application code, components, test files, journeys, configuration, and changed source files. Prettier's check passes for every changed JavaScript/Vue file. There is no frontend typecheck script or TypeScript configuration; the backend-only typecheck is outside this change.

## Exact lifecycle-script decisions

The installed npm **11.19.0** documentation and implementation were inspected alongside its [official versioned package policy documentation](https://raw.githubusercontent.com/npm/cli/v11.19.0/docs/lib/content/configuring-npm/package-json.md) and [install-scripts command documentation](https://docs.npmjs.com/cli/v11/commands/npm-install-scripts/). `npm install-scripts approve vue-demi @parcel/watcher` wrote exact-version `allowScripts` entries into the project manifest. `.npmrc` enables `strict-allow-scripts=true`, making a new unreviewed script version fail installation. Both Dockerfiles now copy `.npmrc` before `npm ci`, preserving engine enforcement and the same policy in containers.

| Exact package | Inspected lifecycle implementation and dependency path | Decision |
| --- | --- | --- |
| `vue-demi@0.14.10` | Pinia 2.3.0 → vue-demi. `postinstall` invokes `scripts/postinstall.js` inside a catch-all wrapper. That file reads installed Vue's version and calls `scripts/utils.js` to copy the selected CJS, ESM and declaration files into `lib`. Vue 2, 2.7 and 3 take separate branches. | **Approve exact version.** Vue 3 selection is required for the Pinia compatibility boundary. Inspecting the wrapper alone or trusting its exit status would miss selection failures. Runtime checks confirm `isVue3=true`, `isVue2=false`, version 3.5.42. |
| `@parcel/watcher@2.5.1` | Sass 1.89.1 → optional watcher. `install` invokes `scripts/build-from-source.js`, which only spawns `node-gyp rebuild` when `npm_config_build_from_source === 'true'`. `index.js` selects a platform/architecture/libc optional prebuild, then falls back to local Release/Debug binaries. | **Approve exact version.** It is a no-op on the supported prebuilt environments and retains the intentional source-build path. No network download is performed by this script. Local Linux x64 glibc and Alpine x64 musl load their corresponding 2.5.1 prebuilds and receive real file updates. |

Neither package changed version during resolution. Source-building is not required or exercised on these platforms; other OS/architecture combinations are not certified by this pass. Optional platform packages must remain installed.

On any version change, inspect the new package's actual scripts and dependency path again, then deliberately update its exact approval and rerun installation/runtime checks. Do not use blanket approval or automatically copy old approvals to new versions. An isolated copy with the vue-demi approval changed to `0.14.9` failed offline `npm ci` with **ESTRICTALLOWSCRIPTS**, naming unresolved `vue-demi@0.14.10`; this confirms that stale approvals force renewed review. `npm install-scripts ls` reports no unreviewed scripts for the final project.

## Verification results and reproduction

All checks used Node **24.20.0**, npm **11.19.0**, and the final dependency set. The declared `npm@11.19.0`, Node/npm engine bounds, and Node version selection remain unchanged.

A local `npm ci` removed previous dependency artifacts and used a dedicated cache plus distinct empty user/global npmrc files. Both reviewed script commands appeared in foreground output and completed. There were no unsupported ESLint or undeclared-approval warnings, and npm reported zero vulnerabilities. No user-level approval, environment policy bypass, script disabling, or forced peer resolution was needed.

From `frontend`, with Node 24 on PATH:

```bash
# Supply two distinct empty files for npm's user and global config.
touch /tmp/owlculus-maintenance-user.npmrc /tmp/owlculus-maintenance-global.npmrc
npm ci --userconfig=/tmp/owlculus-maintenance-user.npmrc --globalconfig=/tmp/owlculus-maintenance-global.npmrc --cache=/tmp/owlculus-maintenance-npm-cache --foreground-scripts
npm ls --all
npm install-scripts ls
./node_modules/.bin/eslint .
node scripts/verify-dependency-maintenance.mjs
npm run test:unit -- --run src/stores/__tests__/auth.test.js src/components/__tests__/ApiKeyManagementCard.test.js src/components/__tests__/Vuetify4PublicSeams.test.js src/composables/__tests__/useApiKeys.test.js
npm run build
```

The three existing files pass **8 tests**; the new API-key error-boundary file passes **3 parameterized cases**, each checking server-detail and fallback messages, original cause, and cleared pending state. No full test suite was run. The maintenance smoke passes locally and in the development and production Alpine builders: Vue 3 selection, Sass compilation, two separate native watcher edit notifications and recompilations, and lint integration probes.

From the repository root:

```bash
docker build --no-cache --progress=plain -f frontend/Dockerfile.dev -t owlculus-maintenance-dev frontend
docker build --no-cache --progress=plain -f frontend/Dockerfile -t owlculus-maintenance-prod .
docker build --progress=plain --target frontend-builder -f frontend/Dockerfile -t owlculus-maintenance-builder .
docker run --rm owlculus-maintenance-dev node scripts/verify-dependency-maintenance.mjs
docker run --rm owlculus-maintenance-builder node scripts/verify-dependency-maintenance.mjs
```

Both no-cache image installations passed without the targeted warnings. The production asset build and both Caddy configuration validations passed; the production image still serves static assets using Caddy. The development smoke ran as its existing non-root user. During verification the final expanded smoke script was mounted read-only into the development image; the production builder contained it directly. Both container dependency trees passed `npm ls --all`. These are local image builds, not deployments.

Remaining unrelated output: 22 baseline Playwright warnings, Vite's mixed static/dynamic `GenericPluginParams.vue` import and >500 kB chunk warnings, npm's optional new-major notice, and existing Caddy validation notices about proxy headers/HTTP-only mode. None were suppressed. Full browser journeys were not rerun for this dependency/configuration maintenance; the prior Vite migration retains its browser evidence.

Execution logs for this pass were saved under `/tmp/owlculus-maintenance-*` (ci, lint-before/after, peers, tests, build, Alpine builds/smokes, and stale-policy). This document records durable outcomes; those temporary logs are not required for reproduction.

## Independent review

The code-review skill's parallel standards and specification reviews compared the implementation with starting commit `a1da9b104f6986f22c62b5e7dd8f981771872c75`. **Standards: zero actionable findings. Specification: zero actionable findings.** The standards review checked repository guidance and design smells; the specification review checked the ticket and recorded verification evidence. Final diff whitespace checks pass, and a lockfile comparison confirms every direct application dependency retains its previous resolved version.

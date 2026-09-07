# Throwaway case workspace exploration

Question: how should compact case identity, workspace navigation, and investigative content share the page?

Branch: `codex/prototype-case-workspace-polish`, based on `ui-refresh`.
Spec: `.scratch/case-workspace-polish/spec.md`.
Verdict: **option A selected on 2026-09-07**, with one Runs workspace combining plugin and hunt history. The prototype now reflects that refinement. Production implementation remains separate from this throwaway source.

Run from the repository root:

```sh
npm --prefix frontend run prototype:case-workspace
```

Open <http://127.0.0.1:5174/case/1?variant=A>. This runs the existing Vue/Vuetify app with the original route, shell, auth initialization, active-case switching, and case data fetching. The dedicated local server supplies fictional API responses and blocks backend writes. It needs no backend, credentials, database, or new dependencies. It binds to loopback only. Reload to discard preview edits.

Use the floating bottom bar, its menu, or left/right arrow keys outside editing controls:

| Value | Layout | Question |
| --- | --- | --- |
| `A` | Open workspace | Does a flat surface with horizontal tabs provide enough separation? |
| `B` | Case file | Does a single framed working surface make the case feel more organized? |
| `C` | Workspace rail | Is persistent vertical workspace navigation worth the table width it costs? |
| `original` | Current design | How does the existing stacked layout compare with identical case data? |

C deliberately departs from the spec's horizontal navigation direction and was not selected. Its workspace rail becomes horizontal on narrow screens. All three keep Case details off the landing surface and now share one Runs workspace, with a chronological list and Type column for plugin and hunt history. The accepted order is Entities, Evidence, Tasks, Runs, Notes. Existing hunt role restrictions still apply within Runs.

Try entity search, type filters, sorting, pagination, selection, record previews, adding/removing sample entities, evidence folders and rename, upload placement, task completion, Notes editing/save/cancel, the details panel, and its nested edit/membership dialogs. Use the real sidebar theme toggle and the second active case to inspect a long title and many assigned users. Drafts and working state survive switches among A/B/C. Switching case or visiting the original baseline resets preview state.

The information button renders current state and design intent. State is also printed to the console. The existing app still remembers its theme and active-case preference on this separate localhost origin; preview business data remains in memory.

Forms, exports, file content, plugin results, and task/hunt interactions are deliberately simplified previews. Plugin waiting, cancellation, recovery, and real persistence are not implemented or verified here. Notes reuse the real editor in manual mode; preview save only updates memory. Production behavior must be implemented and verified separately after a design decision.

The preview mounts only when the dedicated runner sets a development flag. The regular dev command and production build use the original dashboard. Production output excludes prototype components and fixtures.

Browser inspection covered all layouts at 1440×900, 1366×768, 3440×1440, and 390×844, plus light/dark themes, details, a long case title, and draft retention across tab/layout switches. No new test suite was added. Targeted ESLint/Stylelint and the regular production build were used as runnable-code checks.

The selected direction is recorded in the local spec and prototype issue. Rewrite the validated option A layout and combined Runs history for production. Retain this branch as the primary source; do not merge the throwaway components into the implementation branch. Original alternatives remain available at commit `4e4f384`.

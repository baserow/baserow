# Project conventions

The "we do this here" rules. These are what reviewers will keep asking for if
you don't already know them. Read once on your first day; refer back when a
review comment surprises you.

This page is opinionated and short. The rationale matters in edge cases, so
each rule includes a brief **Why** where it isn't self-evident — knowing the
reason is how you handle the cases the rule didn't anticipate.

For the broader code-style settings (linters, formatters, line length) see
[Code quality](code-quality.md). For the PR workflow itself see
[Engineering workflow](engineering-workflow.md).

## Git

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/). The PR
title becomes the commit message in `develop`, so this applies to PR titles
too. Allowed prefixes: `fix:`, `feat:`, `chore:`, `docs:`. Optional scope:
`fix(grid):`, `feat(formulas):`, `chore(deps):`.

- `fix:` — bug fix.
- `feat:` — new functionality or visible change in behaviour.
- `chore:` — refactor, dependency bump, build-system change, no behaviour
  change.
- `docs:` — documentation only.

Keep the title under ~70 characters and focused on intent, not files touched.

### Branch naming

Branch off `develop` unless told otherwise. Suggested patterns:

- `fix/<issue-number>-short-description`
- `feature/<short-description>` or `feat/<short-description>`
- `chore/<short-description>`
- `docs/<short-description>`

## Python

### Logging — always loguru

```python
from loguru import logger
```

Never `import logging` / `logging.getLogger(__name__)` in new code. The
codebase has been migrated; new stdlib-`logging` calls drift back from
that.

**Why:** structured-log output, single configuration point, free
context binding (`logger.bind(workspace_id=...)`).

### Type hints — everywhere

Annotate parameters and return types on every function and method, including
internal helpers. Use `from __future__ import annotations` at the top of new
files so forward references work without quoting.

**Why:** the DRF→Bolt migration is type-driven; missing hints make
mechanical refactors much harder. Tests, IDE refactors, and code review
all rely on the types being there.

### Imports — hoist to the top of the file

Put all imports at the top of the module. **Do not** drop an `import X`
inside a function unless you have a concrete reason:

- A genuine circular import (write a comment naming the cycle).
- A heavy import you genuinely want lazy (write a comment saying why).
- A conditional import gated by a flag or platform check.

If none of those apply, the import belongs at the top.

**Why:** top-of-file imports surface dependencies at a glance, make
unused-import linting work, and prevent surprising import-time work from
hiding inside hot paths.

### Comments — why, not what

- **Default: no comment.** Well-named identifiers already document *what*
  the code does.
- **Add a comment** only when the *why* is non-obvious: a hidden constraint,
  a workaround for a specific bug, behaviour that would surprise a reader.
- **Never explain what the code does** — `# increment counter` next to
  `counter += 1` is noise.
- **Never reference removed or old code** — no `# was previously X`, no
  `# replaces Y`, no `# do not use this, use Z instead`. That information
  belongs in the PR description and rots immediately as the codebase
  evolves.
- **Don't reference the current task or caller** — no `# used by X`, no
  `# added for the Y migration`. Those become stale the moment the
  context changes.
- **No multi-paragraph docstrings, no multi-line comment blocks.** One short
  line max if you must.

### Linting and formatting

Backend code targets Python 3.14, 4-space indentation, 88-character line
length, formatted and linted with Ruff. From `backend/`:

```bash
just fix       # format + auto-fix
just lint      # check only
```

CI runs the same commands. Don't bypass with `# noqa` unless the
suppression has a comment explaining why.

### Tests — always via `just`

Run tests through the recipe, not raw pytest. From `backend/`:

```bash
just test                             # all backend tests
just test tests/path/                 # one path
just test -n=auto                     # parallel
just test-coverage                    # with coverage
```

**Why:** the recipe sets `PYTHONPATH`, env vars, and the right Python; raw
`pytest` will give different results, especially on Postgres-dependent
tests.

Same applies to the frontend (`just test` from `web-frontend/`) and e2e
(`just test` from `e2e-tests/`). Don't run `yarn jest`, `playwright test`,
`pytest`, `ruff`, etc. directly — the recipes are the contract.

If you'd rather work from the repo root, use the `b` / `f` prefix (`just
b test`, `just f test`) or the no-prefix form (`just test`) to run both
suites. See [justfile reference](justfile.md#how-to-invoke-the-three-styles)
for the full convention.

Test file names: `test_<thing>.py` (preferred) or `<thing>_test.py`. Mirror
the source layout under `backend/tests/baserow/...`.

## Frontend

### Vue 3 render functions

Render functions must use Vue 3 semantics. Import `h` from `vue` explicitly
rather than expecting it as a `render(h)` argument:

```javascript
import { h } from 'vue'

export default {
  render() {
    return h('div', { class: 'foo' }, this.$slots.default())
  },
}
```

**Why:** the Vue 2 signature (`render(h) { return h(...) }`) silently breaks
under Vue 3 — `h` is `undefined` at runtime and templates render as empty.
This catches people coming from older parts of the codebase.

### JSX file extensions

Any frontend file containing JSX must use `.jsx` or `.tsx` extension; plain
`.js` / `.ts` files will not be parsed for JSX by Vite. Rename the file when
you introduce JSX into it.

### Locales — only edit `en.json`

When adding or changing user-facing strings, edit **only**
`web-frontend/.../locales/en.json` (and the equivalent files in `premium/`
and `enterprise/`). Do **not** edit `de.json`, `fr.json`, `es.json`, or any
other locale file.

**Why:** Weblate manages translations into all other languages from the
English source. Manually edited non-en locales get overwritten by the next
Weblate sync, your translation work disappears, and the Weblate diff
becomes confusing.

### SCSS — BEM naming

Follow the existing BEM-style block / element / modifier naming in
`web-frontend/modules/`. Don't add ad-hoc utility classes. The component
library has tokens — use them rather than hard-coding values.

### Tests and lint — `just` recipes

From `web-frontend/`:

```bash
just test                  # all frontend tests
just yarn test:core …      # single test
just lint                  # check
just fix                   # auto-fix
```

## Documentation

### Don't duplicate; link

If a concept is already explained in another doc, link to it instead of
re-explaining. Duplicated explanations drift out of sync, and an out-of-sync
explanation is worse than no explanation.

When you find yourself paraphrasing another doc, stop and link to it. If
the existing doc isn't quite what you need, *fix the existing doc* rather
than writing a near-duplicate.

### Doc comments

The "why, not what" rule for code applies here too. Don't write doc
paragraphs that describe what a function does when the type hints already
say it. Spend the words on the things types and identifiers can't
capture: invariants, ordering, side effects, edge-case behaviour.

## Quick reference

| Rule | TL;DR |
|---|---|
| Logger | `from loguru import logger`, never `import logging`. |
| Types | Annotate everything. `from __future__ import annotations` at the top of new files. |
| Imports | Top of the file. Local imports need a concrete reason in a comment. |
| Comments | Default to no comment. If needed, document only non-obvious *why*, never *what* (and never removed code or callers). |
| Commits | Conventional Commits. No `Co-Authored-By:` lines. No auto-commit. |
| Branches | `fix/`, `feat/`, `chore/`, `docs/` off `develop`. |
| Backend tests | From `backend/`: `just test …` — never raw `pytest`. |
| Frontend tests | From `web-frontend/`: `just test …` — never raw `yarn test`. |
| E2E tests | From `e2e-tests/`: `just test …` — never raw `playwright`. |
| Lint/format | `just fix` / `just lint` from the component dir; or `just b/f fix/lint` from root. |
| Locales | Only edit `en.json`. Weblate owns the rest. |
| SCSS | BEM naming. Use design tokens, not hard-coded values. |
| Docs | Link, don't duplicate. |

## Related

- [Engineering workflow](engineering-workflow.md) — branches, PRs, reviews.
- [Code quality](code-quality.md) — linter configuration, line lengths,
  what CI runs.
- [Skills](skills-index.md) — pre-built workflows for common tasks
  (writing tests, adding env vars, creating a changelog).

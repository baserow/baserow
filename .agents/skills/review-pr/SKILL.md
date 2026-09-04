---
name: review-pr
description: Review a Baserow pull request, branch, or diff against `develop` the way the maintainers do. Use when asked to review, deeply review, re-review, or triage review comments on a PR, including follow-up rounds on the same PR.
---

# Review a Baserow Pull Request

The deliverable is a report for the person who asked, written so that every finding can be pasted as a PR comment on a specific line. Never post to GitHub unless explicitly asked.

A review has four phases, in this order. Do not judge code style before the change is understood and verified.

Read `checklist.md` (what to check) and `report-template.md` (what to produce) in this directory before starting.

## Setup

- Work in the current worktree. Never switch branches in the main clone.
- `gh pr view <N> --json title,body,author,baseRefName,headRefName,additions,deletions,changedFiles` and `gh pr diff <N>`.
- Get the code locally with `gh pr checkout <N>`, or `git fetch origin pull/<N>/head:pr-<N> && git switch pr-<N>` when the branch name is taken by another worktree.
- `gh issue view <id>` for every issue referenced in the PR body.
- Stacked PR: the base is the parent branch, so `gh pr diff` already shows only this layer. Review the layer, and check the parent's state (open, merged, changed since).
- `just b test` splits its arguments on spaces: pass explicit test paths or node ids rather than a quoted `-k` expression, and add `--tb=short` when capturing assertion values for a repro.

## Phase 1: Understand

Write, in three sentences, the problem, the intended behaviour, and how the diff solves it. Sources: PR description, linked issue, the changelog entry under `changelog/entries/unreleased/`, any ADR under `docs/decisions/`.

Then establish:

- **Feature flag.** Grep the diff for `feature_flag_is_enabled` and `featureFlagIsEnabled`, and check `docs/development/feature-flags.md`. This decides the merge policy in Phase 4.
- **Scope.** Backend, frontend, premium, enterprise, migrations, public API, import/export, websocket payloads, e2e.
- **Claims.** Every statement in the PR description ("no behaviour change", "~99% smaller payload", "tested with 1M rows") is a claim to verify in Phase 2.

If the problem cannot be reconstructed from PR, issue, and code, that is the first finding (Blocking / Medium). State the gap, then continue under an explicit assumption.

## Phase 2: Verify it works

Verification means running, not reading.

1. Run the tests the diff touches through the repo recipes: `just b test <path>`, `just f test <path>`, `just e2e test <path>`. Report what ran and the result. Never write "tests pass" for tests that did not run.
2. Walk the happy path end to end: API view, handler, model, signals, websocket, frontend store, component. For UI changes start this worktree's stack (`just dc-dev up -d`, ports in `.env.docker-dev`) and drive it in the browser, with the feature flag on and off.
3. Walk the edge angles and intersections in `checklist.md` § Functional. Baserow bugs live in lifecycle paths (duplicate, import/export, trash/restore, undo/redo, snapshots), in public and restricted views, and in mixed-version deploys far more often than in the main flow.
4. Reproduce every suspected bug: a failing test, a shell snippet, a request, or numbered UI steps. A finding without a repro or a traced call chain is a question, not a finding.
5. Check whether each bug also exists on `origin/develop` (`git show origin/develop:<path>`, or a throwaway worktree). Pre-existing bugs go to their own report section and never block the PR, unless this PR's change makes them worse or newly reachable; then they are this PR's finding.

## Phase 3: Review the code

Non-negotiables, all layers:

- Smallest diff that solves the problem. No unrelated hunks, no plumbing for a later PR, no leftovers (debug output, commented code, TODOs, dead helpers and their tests).
- Names carry the contract: a method does exactly what its signature says, no hidden side effects, one term per concept, existing Baserow terms not reused for new concepts.
- Methods short and single-purpose. Complex logic is extracted into a named method whose docstring explains the what, with a test proving it.
- Comments are at most two lines and explain a non-obvious why. A comment that narrates the code is a finding; so is a stale or wrong one.
- Reuse before build: existing handlers, helpers, registry hooks, and library primitives (celery-singleton, `local_cache`, `str_to_bool`, advocate, `schema_editor`) over hand-rolled versions.
- No guards for states that cannot occur (`?.`, `hasattr`, `if not x`). Every guard needs a scenario; otherwise fail loudly.

Backend:

- Every new or touched function has precise type hints and a reST docstring with `:param`, `:return`, and `:raises` where applicable.
- Prefer immutable, structured data (dataclass, `TypedDict`, `NamedTuple`) over passing and mutating plain dicts, and idempotent methods over stateful ones. Suggest, do not block, unless it caused a bug.
- Boundaries: core never imports `baserow_premium` or `baserow_enterprise` outside `if TYPE_CHECKING:`; premium never imports enterprise; `contrib/database` never imports builder, automation, or dashboard; builder and automation never import each other. Serializers in `serializers.py`, action types in `actions.py`, registries in `registries.py`, type subclasses in `*_types.py`, premium and enterprise settings in their own `config/settings/settings.py`.
- Migrations are zero-downtime: new fields have `db_default`, nothing is renamed or dropped while the previous version still runs, data migrations are justified in the PR with a realistic scenario and a test. `just b check-migrations` is clean. One migration per branch: merge into it instead of adding another.
- Translatable strings (`_()`) added or changed: `just b make-translations` was run and the `.po` files are in the diff.

Frontend:

- Copy only in `en.json` files. Any other locale file in the diff is a finding.
- SCSS in a dedicated file imported through the bundle, BEM classes, `$palette-*` variables, no `<style>` blocks in components.
- Frontend rules mirror backend rules (permissions, emptiness, validation). A divergence is a bug, not a style issue.

Security, every PR (details in `checklist.md` § Security): any URL the server fetches goes through advocate; anything rendered from user input is escaped; secrets are write-only and never returned to the UI or usable by another user; every new endpoint checks permission with the right operation type and workspace scoping.

Compatibility, every PR: SaaS runs `develop`, self-hosters run older releases, and production deploys roll. A new frontend must work against the previous backend and vice versa. Renamed API URLs, changed payloads, changed import/export formats, new Celery task names, and changed websocket events need a flag, a compatibility path, or a `breaking_change` changelog entry.

Tests: short, direct, one behaviour each, shared fixtures (`data_fixture`, `api_client`), a docstring only for a non-obvious reason. Every fix and every edge case raised in review gets a regression test that fails on the old code. Assertions prove the behaviour, not that code ran.

Docs: a new env var is in `docs/installation/configuration.md`, `.env.example`, and the docker-compose files. A new concept, public behaviour, or architectural decision gets a doc: an ADR in `docs/decisions/`, a technical doc in `docs/technical/`, or a user guide. User-facing changes get a changelog entry via `just changelog add`.

## Phase 4: Report

Use `report-template.md`. Order findings by severity. Each one has the file and line, the issue, the consequence, a repro for bugs, an alternative when one exists, and the comment to post.

Severity:

- **Blocking / High.** Security hole, data loss or corruption, broken happy path, non-zero-downtime migration, boundary violation, backward-incompatible change without a flag, secret exposure.
- **Blocking / Medium.** Edge-case bug with a repro, missing regression test, silent failure or fallback, wrong layer or duplicated logic that will drift, unverifiable PR claim, missing docs for a new env var or concept.
- **Minor / Low.** Type hints, docstrings, narrating comments, naming, small duplication, leftovers, missing changelog entry.
- **Nit.** Formatting, wording, preference. Optional by definition.
- **Non-blocking.** Questions and design alternatives the author may decline.
- **Follow-up candidates.** Work worth its own PR, under the merge policy below.
- **Pre-existing.** Verified on `develop` and not made worse by this PR. Recorded, never blocking.

Merge policy:

- Behind a feature flag, and the PR is large or hard to retest: Medium findings, and High ones that are neither security nor data loss, may move to a follow-up PR, provided it lands before the flag is removed. Say so in the verdict and ask for a tracked issue.
- Not behind a feature flag: nothing broken merges into `develop`, because SaaS deploys from it. Propose a stacked PR with the fix on top of this branch, and state that the base PR must not be merged alone.

End with what was run, what was not and why, and residual uncertainty. "No findings" is a valid outcome and must be stated explicitly.

## Comment style

- One to four sentences. A question is fine ("Is there a reason we...?", "Wdyt of...?") as long as the concrete alternative is in the same comment.
- Say the consequence, not the rule: "old workers drop this task name during a rolling deploy" beats "this is not backward compatible".
- Simple words, polite, no "you should". Point to the existing pattern to copy, by file and function.
- Bugs come with a repro: numbered UI steps, a pytest or JS snippet, or a request. Small fixes come as a GitHub `suggestion` block.
- Prefix optional comments with `[minor]`, `[nit]`, or `[non-blocking]`. An untagged comment is expected to be addressed.
- One ask per comment. Stacked asks become separate threads.
- The key number or mechanism goes in the comment itself ("9 minutes for 8k workspaces is 67 ms each"), not only in the report detail.

## Red flags

Stop and fix the review if any of these is true:

- A finding has no repro and no traced call chain.
- "Tests pass" appears without a `just` command that ran.
- A pre-existing bug sits in a blocking section.
- A convention is reported without a line where it is broken.
- Nits outnumber the verification section.

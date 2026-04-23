---
name: create-changelog
description: Generate a changelog entry for the current Git branch by inspecting changed files, classifying the domain and type, writing a short public-friendly message, and running `just changelog add` after the user confirms. Use this skill whenever the user asks to "create a changelog", "add a changelog entry", "changelog this branch", "write changelog", or otherwise signals they want to record what their branch changes — even if they don't mention `just` or the exact command.
---

# create-changelog

Create a changelog entry for the work on the current Git branch. The entry is registered by running:

```
just changelog add --domain {domain} --type {type} --message '{message}'
```

## Workflow

Follow these steps in order. Do not skip ahead — the user confirms before anything is committed.

### 1. Gather the diff

Run these commands from the repository root to understand what has changed on this branch relative to `develop`:

```bash
git rev-parse --abbrev-ref HEAD
git diff --name-status develop...HEAD
git diff --stat develop...HEAD
git log develop..HEAD --oneline
```

`develop...HEAD` (three dots) gives the changes introduced on this branch since it diverged from `develop`, which is what a changelog entry should describe.

If any of the following is true, stop and tell the user there's nothing to changelog:

- `git diff --name-status develop...HEAD` is empty.
- The current branch is `develop` itself, or is `main`/`master`.
- `develop` does not exist as a ref (in which case mention it and ask how they'd like to proceed).

If the diff is large enough that the file list alone isn't informative, also peek at `git diff develop...HEAD -- <path>` for a few of the most-changed files to get a sense of the substance of the change. Prefer looking at a handful of representative files over dumping the entire diff.

### 2. Pick the domain

The domain must be exactly one of: `core`, `database`, `dashboard`, `builder`, `automation`, `integration`. These correspond to modules in the codebase.

Choose the domain with the most changed files. Use directory names and file paths as the primary signal — e.g. files under a `dashboard/` directory belong to `dashboard`. If paths are ambiguous, fall back to the substance of the changes (e.g. migration files → `database`, webhook/third-party API code → `integration`).

If there's a close tie, prefer the domain that contains the change with the most lines modified, or the one the branch name and commit messages most clearly point at. Don't overthink it — pick the single best match.

### 3. Pick the type

The type must be exactly one of: `bug`, `feature`, `refactor`, `breaking_change`.

Rough guide:

- `bug` — fixes incorrect behavior. Signals: commit messages with "fix", "bug", "regression"; small targeted changes; tests added alongside a fix.
- `feature` — adds capability that wasn't there before. Signals: new files, new endpoints, new UI, new configuration options.
- `refactor` — reshapes existing code without changing behavior. Signals: moves/renames, no new functionality, no bug being fixed, tests largely unchanged.
- `breaking_change` — changes that require consumers to update. Signals: removed/renamed public APIs, changed function signatures, database migrations that drop columns, config format changes.

A breaking change beats the other labels when it applies — if a refactor removes a public function, it's a `breaking_change`. Otherwise, pick the single best fit and move on.

### 4. Write the message

The message describes what changed, in plain English, for a mixed audience of developers and non-technical users reading a public changelog.

Rules:

- **Max 100 characters**, including spaces. Count them.
- Plain English, no jargon, no internal code names, no file paths, no class names.
- Present tense, sentence case, no trailing period. Start with a verb when natural.
- Describe the user-visible effect, not the implementation. "Speeds up dashboard loading" beats "Adds index to dashboard_widgets.user_id".
- Don't start with the type or domain (e.g. don't write "Fix: ..." — the type and domain are separate fields).
- Single line, no newlines.

**Examples:**

Good:
- `Dashboards now load faster when you have many widgets`
- `Fixes an error that could lose changes when saving automations`
- `Adds a bulk import option for contacts`

Too technical:
- `Refactor DashboardWidget.render() to use memoization`
- `Patch NPE in AutomationSaver.persist()`

Too vague:
- `Various improvements`
- `Bug fixes`

### 5. Show the proposal and get confirmation

Present the chosen values to the user in this exact shape so they're easy to scan:

```
Domain:  <domain>
Type:    <type>
Message: <message>
```

Follow with a one- or two-sentence rationale explaining *why* you picked that domain and type (e.g. "7 of 9 changed files are under `builder/`, and the branch adds a new step type, so I called it a new feature.") and then the full command that will be run:

```
just changelog add --domain <domain> --type <type> --message '<message>'
```

Ask the user to confirm, or to tell you what to change. If they ask for changes, redo whichever steps are affected and present an updated proposal — don't run the command until the user explicitly confirms.

### 6. Execute

Once the user confirms, run the command:

```bash
just changelog add --domain <domain> --type <type> --message '<message>'
```

Wrap the message in single quotes so apostrophes, spaces, and punctuation pass through correctly. If the message itself contains a single quote, close-escape-open it (`'\''`) or rewrite the message to avoid it — preferably the latter, since changelog messages rarely need apostrophes.

The issue number is automatically extracted from the branch name (e.g. a branch named `1234-fix-something` yields issue `1234`). If no issue number is found in the branch name, the entry is created without one.

Show the command's output to the user and confirm it succeeded. If `just` errors (for example, the arguments aren't accepted), surface the error and offer to adjust and retry.

## Notes

- If the user runs this skill multiple times in one session with different intents, re-run the diff — don't reuse cached results, because the branch state may have changed.

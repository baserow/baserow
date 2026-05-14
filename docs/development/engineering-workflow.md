# Engineering workflow

How we work day to day: issues → branches → pull requests → review → merge. This
is the rule of thumb; specific exceptions (security fixes, enterprise release
windows, hotfixes) have their own runbooks.

## Issues

We use [GitHub Issues](https://github.com/baserow/baserow/issues). New issues are
opened through one of two templates from the
[New issue page](https://github.com/baserow/baserow/issues/new/choose):

- **🪲 Bug Report** (`.github/ISSUE_TEMPLATE/bug.yml`) — auto-applies the
  `bug 🪲` and `needs feedback ⚠️` labels.
- **💡 Feature Request** (`.github/ISSUE_TEMPLATE/feature_request.yml`) —
  auto-applies the `feature request 💡` and `needs feedback ⚠️` labels.

Blank issues are disabled by default; vague ideas go to the
[community forum](https://community.baserow.io/) first.

There is no "maintenance" template — refactors, dependency upgrades and pure tech
debt are typically tracked directly in pull requests rather than as separate
issues.

### Labels worth knowing

**Domain labels** identify which team's expertise is needed. Exactly one is
usually applied:

- `database 🗄️` — database module.
- `application 📱` — application builder.
- `automation 🤖` — automations.
- `dashboard 📈` — dashboards.
- `core 🔩` — only core code; no contrib expertise required.
- `devops 👨‍🔧` — infra, CI, deployment, install methods.
- `integration 🔗` — Zapier and other external integrations.

**Type labels** are mostly auto-applied by the issue templates:

- `bug 🪲` — bugs.
- `feature request 💡` — feature requests.
- `AI` — AI-related code.

**Triage / lifecycle labels:**

- `needs feedback ⚠️` — applied automatically; means a maintainer hasn't
  reviewed it yet.
- `up-next` — triaged and prioritized; safe to pick from when starting new work.
- `good first issue` — simple starting issues. Note: the label is sparsely
  maintained, so prefer `up-next` + domain + recency when looking for work.
- `needs ux design 🎨` — blocked on UI/UX design.
- `external contribution` — opened by a community contributor.
- `gitlab issue` — migrated from the old GitLab tracker; ignore for new triage.

**Priority labels:** `p0` (high) → `p3` (lowest).

**Size label:** `size:xl` — represents over 10 days of work; issues with this
label must be split into smaller tasks.

**Bot-managed labels** (auto-applied by dependabot etc.): `dependencies`,
`python`, `python:uv`, `javascript`.

## Branches

Branch off `develop` unless instructed otherwise. Suggested patterns, matching
existing branch names in the repo:

- `fix/<issue-number>-short-description` — bug fixes.
- `feature/<short-description>` or `feat/<short-description>` — features.
- `chore/<short-description>` — maintenance / chore.
- `docs/<short-description>` — documentation.

## Pull request workflow

1. **Open the PR in draft.** This signals "work in progress; CI is welcome to run
   but don't review yet". Use the
   [PR template](https://github.com/baserow/baserow/blob/master/.github/PULL_REQUEST_TEMPLATE.md).
2. **Mark ready for review** when it's genuinely ready. Either request a reviewer
   directly or drop a message in the review channel asking for one.
3. **Reviewers always start a formal review** rather than leaving loose comments.
   A formal review communicates intent (approve / request changes) and groups
   feedback.
4. **Working through feedback?** Put the PR back into draft state while you do
   the work, then re-mark as ready when you've addressed the comments and
   re-request a review.
5. **Merge** once approvals are in and CI is green.

## What the PR template asks for

The repo's PR template (`.github/PULL_REQUEST_TEMPLATE.md`) is the canonical
list. The items worth remembering:

- A short summary of what the PR does.
- A short test plan a reviewer can follow.
- A changelog entry added under `changelog/entries/unreleased` using
  `changelog/src/changelog.py`.
- Premium / enterprise code separated into the right folder (`premium/` or
  `enterprise/` — never in `core` or `contrib`).
- Tested in latest Chrome and Firefox for frontend changes.
- Documentation updated when behaviour or surface area changes.
- API docs (redoc + the custom token-API docs page in
  `web-frontend/modules/database/pages/APIDocsDatabase.vue`) updated for REST
  API changes.
- Performance check for tables at 100k+ rows / 100+ fields when relevant.
- Security impact considered.

## Useful GitHub queries

- [Pull requests sorted by latest activity](https://github.com/baserow/baserow/pulls?q=is%3Apr+is%3Aopen+sort%3Aupdated-desc)
- [Pull requests waiting on my review](https://github.com/baserow/baserow/pulls/review-requested/%40me)
- [Pull requests I authored](https://github.com/baserow/baserow/pulls/%40me)
- [Issues in `database 🗄️` labeled `up-next`](https://github.com/baserow/baserow/issues?q=is%3Aopen+is%3Aissue+label%3A%22database+%F0%9F%97%84%EF%B8%8F%22+label%3Aup-next)

## Related

- [Code quality](code-quality.md) — formatting, linting and quality bar.
- [Running tests](running-tests.md) — how to run the backend test suite.
- [E2E testing](e2e-testing.md) — when and how to add Playwright tests.
- [CI/CD](ci-cd.md) — what runs on every PR.
- [CONTRIBUTING.md](https://github.com/baserow/baserow/blob/master/CONTRIBUTING.md)
  — repo-wide contribution standards.

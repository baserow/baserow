# Engineering workflow

How we work day to day: issues → branches → pull requests → review → merge. This
is the rule of thumb; specific exceptions (security fixes, enterprise release
windows, hotfixes) have their own runbooks.

## Issues

We use [GitHub Issues](https://github.com/baserow/baserow/issues). Bugs and
feature requests should use the issue templates so GitHub's issue type is set
correctly. Refactors, dependency bumps, docs, CI work, and similar tasks can use
a blank issue and be typed during triage.

The durable rules:

- Concrete bug reports and feature requests belong in GitHub issues.
- Vague product ideas usually start in the
  [community forum](https://community.baserow.io/).
- Team priority lives in the team's GitHub project, not in a hard-coded label
  list.
- Oversized work should be split before implementation.

Labels and project-board fields change. Trust the live GitHub project for the
current taxonomy.

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

## Related

- [Code quality](code-quality.md) — formatting, linting and quality bar.
- [Running tests](running-tests.md) — how to run the backend test suite.
- [E2E testing](e2e-testing.md) — when and how to add Playwright tests.
- [CI/CD](ci-cd.md) — what runs on every PR.
- [CONTRIBUTING.md](https://github.com/baserow/baserow/blob/master/CONTRIBUTING.md)
  — repo-wide contribution standards.

# Contributing to Baserow

We appreciate your interest in contributing to Baserow. To make the process smooth for everyone, please read these guidelines before opening a pull request.

We're a small team. Creating a PR with some changes is easy — reviewing it thoroughly and ensuring it meets our standards takes significantly more time. These guidelines exist to make sure that effort is well spent on both sides.

## Types of contributions

### Bug fixes

1. **Open a bug issue first** with steps to reproduce and expected behavior
2. If the fix is obvious, open a PR right away. If you're unsure about the expected behavior or the right approach, wait for confirmation on the issue first.

PRs without a corresponding issue will be closed.

### Features and behavior changes

Any PR that adds new functionality or changes existing behavior — no matter how small — requires prior approval.

1. Check [existing issues](https://github.com/baserow/baserow/issues) first — if an approved issue for the feature already exists, reference it in your PR instead of opening a new one. Only open a new feature request if no matching issue exists.
2. **Open a feature request issue** using the [feature request template](https://github.com/baserow/baserow/issues/new?template=feature_request.yml)
3. Describe what you want to build, why and your proposed approach
4. **Wait for explicit approval** from a maintainer before writing code
5. Open your PR referencing the approved issue

PRs for features without an approved issue will be closed. This isn't about gatekeeping — it's about making sure you don't invest time in something that won't be merged.

### Tasks

Tasks cover everything that isn't a feature or bug fix: typo corrections, broken links, documentation updates, refactoring, dependency bumps, etc.

- **Small tasks** where the correctness is obvious on sight (typos, broken links, minor doc edits) can be submitted directly as a PR without an issue.
- **Larger tasks** that touch multiple files or require design decisions need an issue and likely approval, same as features.

If you're unsure, check whether a related issue already exists — if not, open one.

## Before you start

- Make sure your contribution either doesn't require an issue (small task) or has an approved issue (bug fix, feature, or large task). Don't write code before that.
- Check [existing issues](https://github.com/baserow/baserow/issues) to avoid duplicate work
- Fork the repository and create your branch from `develop`
- Read the quality standards below

## Pull request requirements

Your PR title must follow [Conventional Commits](https://www.conventionalcommits.org/) format — it becomes the commit message in our git history. Keep it short and focused on the **intent** of the change, not what files were touched.

Allowed prefixes: `fix:`, `feat:`, `chore:`, `docs:`. An optional scope in parentheses is encouraged: `fix(grid):`, `feat(formulas):`, `chore(deps):`.

Examples:
- `fix(forms): prevent submission with invalid rating value`
- `feat: add Cloudflare Turnstile captcha to auth`
- `chore(deps): bump requests to 2.33.0`
- `docs: update contribution guidelines`

Your PR must also include:

- **A clear description** of what was changed and why
- **How to test it** — steps a reviewer can follow to verify your changes
- **A link to the issue** in the description (e.g., `Closes #123`), when applicable
- **Tests** — backend changes need tests
- **A changelog entry** generated using the script in `changelog/`

### What will get your PR closed

- **Modifying premium or enterprise code.** The `premium/` and `enterprise/` directories contain licensed code that is not open to external contributions. PRs that touch these directories — including moving code from them into core — will be closed immediately.
- **No linked issue** for bug fixes or features (see above)
- **No description or test instructions**
- **Not following these guidelines** after being asked to

### Size guideline

Aim for focused, well-scoped PRs. As a rough guideline, we look at **lines of useful code (LOUC)** — excluding tests, boilerplate, translations, docs. A PR touching ~10 files with ~10 LOUC each is a reasonable upper bound, but complexity matters more than line count — a few lines in a critical path can be harder to review than hundreds of boilerplate. Tests and docs are excluded from LOUC but still need to be reviewed, so keep them concise and follow existing patterns. We may ask you to split a PR, reduce scope, or remove scope creep at our discretion.

## What happens after you submit

We review PRs as capacity allows.

Possible outcomes:

- **Approved and merged** — your PR meets our standards
- **Changes requested** — we'll list what needs to change. Please respond within 2 weeks; PRs with no activity after that will be closed. You can always reopen later.
- **Closed** — with an explanation of why. This is not personal — it's about priorities, alignment, and capacity. You can reopen if you resolve the issues, or open a fresh PR after incorporating our feedback.

## Quality standards

See [Code quality](docs/development/code-quality.md) for the full list of standards, linters, and testing expectations. The CI pipeline must pass and security impact must be considered.

## License

When you submit code changes, your submissions are understood to be under the same [MIT License](https://choosealicense.com/licenses/mit/) that covers the project.

## Security vulnerabilities

If you find a security vulnerability, please report it privately via email or the contact form at https://baserow.io/contact — do not open a public issue.

## Questions?

For general questions about Baserow, use the [community forum](https://community.baserow.io/).

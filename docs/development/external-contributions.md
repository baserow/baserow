# Handling External Contributions

Internal guidelines for triaging and reviewing pull requests from external contributors.

## Contribution categories

Every external PR falls into one of three categories. The category determines what we require before reviewing.

| Category | Requires issue? | Requires approval? | Can close immediately? |
|----------|----------------|--------------------|-----------------------|
| **Feature** | Yes | Yes (tech lead or product manager) | If no approved issue exists |
| **Bug fix** | Yes (with repro steps) | No, but approach must be sound | If no issue or approach is wrong |
| **Task** (small) | No | No | At our discretion |
| **Task** (large) | Yes | Likely yes | If no issue or approach is wrong |

**Tasks** cover anything that isn't a feature or bug fix: typo corrections, documentation updates, refactoring, dependency bumps, CI improvements, etc. Small tasks (obvious correctness, trivial scope) can go straight to a PR. Larger tasks that touch multiple files or require design decisions need an issue and likely approval, same as features.

## Evaluation criteria

For each PR, assess these criteria. The combination drives the decision — not any single criterion in isolation.

| Criterion | Assessment |
|-----------|-----------|
| **Type** | Bug fix / feature / task (small or large) |
| **Size** | Small (< 10 LOUC) / medium (10-100) / large (> 100). LOUC = lines of useful code, excluding tests, comments, translations, docs and boilerplate |
| **Complexity** | Trivial / moderate / touches high-risk area |
| **Utility** | Addresses known need / nice-to-have / not aligned with roadmap |
| **Approach** | Approved in issue / sound / needs rework / fundamentally wrong |
| **Code quality** | Matches our standards / needs polish / AI slop |
| **Scope** | Open-source only / touches premium or enterprise code |

### Immediate closure rules

Close the PR right away (with the appropriate response template) if any of these apply:

- Touches `premium/` or `enterprise/` code, or moves code from those directories to core
- Feature PR without a pre-approved issue
- Bug fix PR without an issue containing reproduction steps
- Not aligned with product direction
- AI-generated low-quality code with no meaningful effort from the contributor

### Review signals

Favor reviewing when:
- Contributor discussed the approach beforehand and got approval
- Addresses a known, prioritized issue
- Small, well-scoped, well-described
- Code quality is close to what we'd write ourselves

Favor closing when:
- Large PR with no prior discussion
- Reviewing + guiding would cost more than reimplementing
- Contributor shows no willingness to iterate

### Mixed signals

When the assessment is mixed (e.g., good approach but large size, or useful but needs significant rework), discuss with the tech lead before responding.

## Response templates

Use differentiated messages depending on the situation. Do not use the same message for every closure.

### Not aligned / closing

Close the PR immediately. The contributor can still respond on the closed PR.

```
Hi,

Thanks for your contribution. After reviewing this PR, we've decided not to move forward with it because [specific reason: not aligned with our roadmap / addresses a use case we don't plan to support / etc.].

If you'd like to contribute in the future, please check our [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines on how we evaluate contributions.

Thanks for your interest in Baserow.
```

### No prior issue (feature or bug)

Close the PR immediately with a pointer to the process.

```
Hi,

Thanks for taking the time to submit this. [Features require an approved issue / Bug fixes require an issue with reproduction steps] before opening a PR. This helps us align on the approach early and avoid wasted effort on both sides.

Please open an issue first following our [contribution guidelines](../../CONTRIBUTING.md), and we'll take it from there.
```

### Touches premium/enterprise code

Close immediately.

```
Hi,

Thanks for your contribution. Unfortunately, this PR modifies code in the `premium/` or `enterprise/` directories, which are not open to external contributions.

If the rest of your changes are valid for the open-source core, please resubmit a PR without those modifications.
```

### Promising but needs work

Do **not** close. List what's needed and set a deadline.

```
Hi,

Thanks for this PR. The direction looks [good / promising], but it needs some changes before we can merge it:

- [Specific item 1]
- [Specific item 2]
- [...]

Please address these within the next 2 weeks. If we don't hear back, we'll close the PR. You can always reopen it later if you want to pick it back up.

If you'd prefer, you can also ask us to finish it — see the "Help us finish it" section in our [CONTRIBUTING.md](../../CONTRIBUTING.md).
```

### Offering to finish it (proactive)

When we see a promising PR that the contributor may not be able to bring to our standards:

```
Hi,

Thanks for this contribution. The idea and direction are good, but bringing it to our quality standards would require [significant rework / additional changes].

If you'd like, we can take it from here and finish it ourselves. We'd include your name as a contributor in the release. Let us know if that works for you, or if you'd prefer to continue working on it yourself.
```

## Stale PR policy

- After a review with requested changes: wait **2 weeks** for a response
- If no response after 2 weeks: close with a brief message
- The contributor can reopen or submit a new PR later

```
Hi,

Closing this PR due to inactivity. If you'd like to pick this up again, feel free to reopen it or submit a new PR.
```

## "We'll finish it" flow

This can be triggered two ways:
1. The **contributor asks** us to finish their PR
2. We **proactively offer** when the PR is promising but needs more work than the contributor can deliver

### When to accept

- The feature/fix is something we actually want
- The existing code is good enough to build on (not a full rewrite)
- We have capacity to finish it in a reasonable timeframe

### When to decline

- The PR requires a near-complete rewrite
- The feature isn't aligned with our priorities
- We don't have capacity right now

### How to credit

- Mention the contributor by name in the changelog entry
- Include them in release notes as a contributor
- Use co-author in the commit if we build on their code directly

### No guarantees

We don't commit to finishing every PR that's offered. If it's not the right time or requires too many changes, we decline politely and explain why.

## General principles

- **Impact vs. cost**: prioritize PRs where the value is high relative to the review effort
- **Push back early**: it's better to close quickly with clear guidance than to let a PR linger for months
- **Don't leave PRs undecided**: triage within a week, respond within two. Silence is worse than a "no"
- **When in doubt, ask the tech lead**

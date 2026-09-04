---
name: review-pr
description: Review a Baserow pull request, branch, or diff against `develop` the way the maintainers do. Use when asked to review, deeply review, re-review, or triage review comments on a PR, including follow-up rounds on the same PR.
---

# Review a Baserow Pull Request

Produce an evidence-backed report whose findings can be pasted as line comments.
Never post to GitHub unless explicitly asked.

## Review principles

Use these invariants instead of accumulating a universal list of edge cases:

1. **Risk follows semantic reach, not diff size.** Trace every consumer of a
   shared registry, base class, setting, component, payload, or persisted shape.
2. **One concept has one owner and one snapshot.** Resolve mutable facts once and
   pass the same typed value through validation, authorization, accounting,
   execution, metadata, and serialization. Parallel implementations must delegate
   to one contract or prove they cannot drift.
3. **Correctness is a timeline.** Review creation, use, change, failure, retry,
   concurrency, restart, and removal rather than only the final saved state. Every
   derived value needs a producer, source inputs, invalidators, and consumers.
4. **Different meanings need different states.** Do not collapse missing, empty,
   false, zero, inherited, not loaded, invalid, skipped, partial, and failed when
   they cause different behaviour or recovery.
5. **Persistence creates a compatibility contract.** Anything users can save,
   reference, export, cache, or derive from needs a rollout and recovery story when
   its representation or semantics change.
6. **Judge actual effects, not configured intent or proxies.** Authorize before an
   effect, account for work actually attempted, clean up resources actually owned,
   and test the claimed outcome rather than a nearby count or callback.
7. **Assume hostile input and least authority.** A user must not read, alter,
   execute as, or consume resources belonging to a capability they do not have.
   No response, log, trace, event, or fallback may disclose protected context.
8. **Cost is per-unit work multiplied by real fan-out.** Evaluate realistic
   cardinality and concurrency, and bound the complete operation rather than one
   convenient phase.

## Workflow

### 1. Establish the contract

- Work in the current worktree; never switch branches in the main clone.
- Read the PR description and every linked issue. Inspect the diff against its real
  base; for a stack, review only the layer and check the parent state.
- State in three sentences: the problem, intended behaviour, and approach.
- Identify the feature flag, affected products/layers, persisted contracts, trust
  boundaries, expected cardinalities, and every measurable claim.
- Build a semantic reach map for shared primitives. A one-line edit can require a
  wider review than a new isolated module.

Useful commands include:

```bash
gh pr view <N> --json title,body,author,baseRefName,headRefName,additions,deletions,changedFiles
gh pr diff <N>
gh issue view <id>
```

Use `gh pr checkout <N>`, or fetch the pull ref into a dedicated worktree branch
when that name is already checked out elsewhere.

### 2. Route to relevant topics

Read every selected reference completely, and do not load unrelated references.
Select more than one when a change crosses concerns.

- Database module code, its tests or documentation, or an extension/shared contract
  that changes Database tables, fields, rows, views, formulas, data syncs, imports,
  exports, or workflow actions: read
  [references/modules/database.md](references/modules/database.md).
- Backend Python, Django models, APIs, handlers, actions, services, registries, or
  settings: read [references/backend.md](references/backend.md).
- Vue components, stores/composables, browser behaviour, frontend services,
  translations, or SCSS: read [references/frontend.md](references/frontend.md).
- ORM/SQL, indexes, serializers over collections, loops, bulk work, caches,
  generated expressions, background fan-out, payload size, or a performance claim:
  read [references/data-performance.md](references/data-performance.md).
- Outbound HTTP/email/SSO/provider calls, user-selected hosts, Celery/Redis, locks,
  retries, scheduling, remote pagination, or asynchronous cleanup: read
  [references/external-io.md](references/external-io.md). Load data-performance too
  when local cardinality drives the remote fan-out.
- Authentication, permissions, licenses, secrets, new endpoints, public/restricted
  data, destructive/admin capabilities, or code that changes how user-controlled
  input, rendered output, files, URLs, or external responses cross a trust boundary:
  read
  [references/security.md](references/security.md).
- Models or stored values, migrations, feature flags, import/export, duplication,
  trash/restore, undo/redo, realtime, Celery, retries, or cache invalidation: read
  [references/state-compatibility.md](references/state-compatibility.md).
- Python or JavaScript dependencies, lockfiles, framework/runtime upgrades, or a
  dependency security advisory: read
  [references/dependencies.md](references/dependencies.md).

For any behavior-affecting change, including CSS or configuration, perform a quick
security and scale screen even when their references are not initially selected:

- Can a lower-privilege actor, crafted input, stale client, or alternate entry point
  reach a protected read or effect, or expose data in output or observability?
- What is the expected number of users, workspaces, rows, fields, elements, actions,
  events, or external calls, and does any cost multiply with it?

If either answer is non-trivial, load the corresponding reference.

### 3. Verify behaviour

- Run the focused tests through the repository `just` recipes. Report the exact
  commands and outcomes; never imply a test ran when it did not.
- Trace the happy path end to end, then test the state transitions and attack/scale
  hypotheses selected by the topic references.
- Reproduce suspected bugs with a failing test, request, query plan, browser steps,
  or a traced call chain. A plausible concern without evidence is a question.
- Check whether each bug exists on `origin/develop`. Pre-existing bugs are recorded
  separately unless the PR worsens or newly exposes them.
- Verify PR claims using the actual effect. Performance claims need representative
  data; security claims need an adversarial path; UI claims need browser behaviour.

`just b test` splits arguments on spaces, so pass explicit paths or node ids rather
than a quoted `-k` expression. Use the worktree's stack and ports for browser checks.

### 4. Report

Read [report-template.md](report-template.md) only when writing the report. Order
findings by impact and include file/line, consequence, evidence, a concrete
alternative when one exists, and ready-to-post wording.

Severity:

- **Blocking / High:** security exposure, cross-tenant or privilege violation, data
  loss/corruption, broken main path, non-zero-downtime migration, or incompatible
  deployed contract.
- **Blocking / Medium:** reproduced edge failure, missing regression for changed
  behaviour, silent fallback, invariant enforced in only some entry points, or an
  important claim that cannot be verified.
- **Minor / Low:** maintainability or repository-convention issue with a concrete
  future cost.
- **Nit / Non-blocking:** optional wording, style, question, or alternative.

Behind a feature flag, a non-security/non-data-loss finding may be tracked before
flag removal when retesting now is disproportionate. Without a flag, broken code
must not land alone; propose a stacked fix and state that the base must not merge by
itself.

## Comment quality

- One ask per comment, usually one to four sentences.
- State the consequence and evidence, not merely the rule.
- Bugs include a repro or traced path; small fixes can include a suggestion block.
- Prefix optional feedback with `[minor]`, `[nit]`, or `[non-blocking]`.
- Do not let nits outnumber functional, security, or scale verification.

Stop and correct the review if a finding lacks evidence, a pre-existing bug is
blocking the PR, or the report says something passed without the command having run.

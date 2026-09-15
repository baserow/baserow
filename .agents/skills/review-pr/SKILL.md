---
name: review-pr
description: Review a Baserow pull request, branch, or diff against its actual base the way the maintainers do. Use when asked to review, deeply review, re-review, or triage review comments on a PR, including follow-up rounds on the same PR.
---

# Review a Baserow Pull Request

Produce an evidence-backed report whose findings can be pasted as line comments.
Explain issues and resolution criteria without applying implementation fixes unless
the user separately requests implementation. Never post to GitHub unless explicitly
asked.

Preserve the author's checkout and existing changes. Keep diagnostic scripts, test
additions, and instrumentation in a temporary directory or isolated review worktree;
do not commit them or leave them in the author's submission. Keep useful evidence
available to the author and report its location and reproduction command.

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

- Use the current worktree when it already matches the revision being reviewed.
  Otherwise create an isolated review worktree at that revision; never switch
  branches in the main clone or overwrite local changes.
- Read the PR description and every linked issue. Inspect the diff against its real
  base; for a stack, review only the layer against its parent, not `develop`.
  Record the base ref, comparison base (merge-base), and head commit. Ensure source,
  diff, and test results refer to those revisions; disclose any local changes.
- For a re-review or comment-triage request, read
  [references/re-review.md](references/re-review.md) before inspecting findings.
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

Fetch missing refs before creating the isolated worktree. Do not run `gh pr checkout`
in the author's checkout; fetching a ref does not require switching that checkout.

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
  Reduce the case to the smallest trigger that preserves the failure; record its
  prerequisites, expected result, and observed result.
- Compare the same reproduction or traced path against the recorded comparison
  base. Pre-existing bugs are recorded separately unless this layer worsens or newly
  exposes them; describe that incremental impact. `develop` is only supplementary
  context when it is not the reviewed layer's base.
- Verify PR claims using the actual effect. Performance claims need representative
  data; security claims need an adversarial path; UI claims need browser behaviour.

`just b test` splits arguments on spaces, so pass explicit paths or node ids rather
than a quoted `-k` expression. Use the worktree's stack and ports for browser checks.

### 4. Report

Read [report-template.md](report-template.md) only when writing the report. Order
findings by impact. Give each finding a stable ID across review rounds, a precise
location, reproducible evidence, consequence, and how the author can verify
resolution. Include concise ready-to-post wording.

Omit suggested alternative directions by default. Include one only when the current
approach has substantial, demonstrated problems and a different approach would
materially reduce those problems or the complexity needed to solve them. Explain
the concrete benefit and relevant tradeoffs, including the cost of changing course.
Another valid implementation or a stylistic preference is not grounds for proposing
a redesign. Preserve a workable approach and focus feedback on the required outcome.

Assess severity and merge impact separately:

- **High:** security exposure, cross-tenant or privilege violation, data
  loss/corruption, broken main path, non-zero-downtime migration, or incompatible
  deployed contract.
- **Medium:** a demonstrated edge failure, unintended fallback, invariant missing
  from a reachable entry point, or an acceptance-critical regression/evidence gap
  with an identified risk.
- **Low:** maintainability or repository-convention issue with a concrete
  future cost.
- **Nit:** optional wording or style feedback.

Explain why a finding blocks merging or can wait. Missing access to a service,
representative data, or credentials is a review limitation, not proof of a defect.
For an acceptance-critical evidence gap, state the guarantee at risk and the exact
verification needed. Use **Incomplete** when unavailable evidence prevents a
defensible verdict; record other confirmed findings normally.

A non-security/non-data-loss finding may be deferred behind a feature flag only
after verifying that the deployed flag state isolates its effects. Check shared
code, unconditional migrations, queued work, alternate entry points, and objects
persisted while enabled. Record the verified flag state, remaining impact, and a
tracked condition requiring resolution before exposure or flag removal. A flag's
existence alone does not justify deferral. Otherwise broken code must not land
alone; a suggested stacked fix must state that the base cannot merge by itself.

## Comment quality

- One ask per comment, usually one to four sentences.
- State the consequence and evidence, not merely the rule.
- Bugs include a repro or traced path. A small local correction within the existing
  approach can use a suggestion block when it clarifies the issue; it does not need
  a suggested-direction section.
- Give an observable resolution criterion when useful; leave implementation choices
  with the author. Link long logs or repro artifacts instead of expanding the comment.
- Prefix optional feedback with `[minor]`, `[nit]`, or `[non-blocking]`.
- Keep optional feedback proportionate to the verified risk; do not manufacture
  findings or pad a clean review with nits.

Stop and correct the review if a finding lacks evidence, a pre-existing bug is
attributed to this layer without incremental impact, or the report says something
passed without the command having run.

## Extend this skill

When adding or changing review rules, read
[references/maintaining.md](references/maintaining.md) for ownership, evidence,
exceptions, and behavioral validation. Ordinary PR reviews do not need that guide.

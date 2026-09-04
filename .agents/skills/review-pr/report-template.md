# Report template

Omit empty finding sections, but always include Verification. Number findings within
each section and order them by impact. Anchor a missing test, document, or PR claim to
the place that should own it, or explicitly to the PR description.

---

# Review: PR #<N> <title>

**Problem and change.** <Problem, intended behavior, and approach in three sentences.>

**Risk map.** <Semantic reach, persisted contracts, trust boundaries, expected scale,
and the review surfaces selected from them.>

**Feature flag:** `<flag>` or none. **Scope:** <affected products and layers>.

**Verdict:** <Approve | Approve with follow-ups | Request changes>. <Apply the flag
and stacking policy in one sentence.>

## Blocking / High

### 1. <Short title>

- **Where:** `backend/src/baserow/.../handler.py:123`
- **Consequence:** <What fails or is exposed, for whom, and under which conditions.>
- **Evidence:** <Repro, request, query plan, browser steps, or traced call chain.>
- **Alternative:** <Smaller or safer design, when useful.>
- **Comment:**
  > <Ready-to-post wording: one ask, one to four sentences.>

## Blocking / Medium

## Minor / Low

## Nits

## Non-blocking

## Follow-up candidates

- <Item, why it can wait, and the issue/merge condition that prevents it being lost.>

## Pre-existing (not caused by this PR)

- <Item and how it was verified on `develop`; suggest a separate issue.>

## Verification

- **Automated:** <exact commands, counts, and results>.
- **Manual:** <real behavior exercised, including flag states where applicable>.
- **Database and scale:** <cardinality, query growth/plan, benchmark, or why not applicable>.
- **Security and misuse:** <actors/attack paths exercised, or why not applicable>.
- **Not run:** <what and why>.
- **Residual uncertainty:** <what remains unverified>.

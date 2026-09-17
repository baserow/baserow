# Report template

Omit empty optional sections, but always include the verdict and Verification. If
there are no actionable findings, say so without implying unperformed checks passed.
Order findings by impact. Assign IDs once across the whole report (`R1`, `R2`, ...),
retain them across review rounds, and never reuse resolved IDs. For imported reviews,
map IDs to the original thread links. Anchor a missing test, document, or PR claim to
the place that should own it, or explicitly to the PR description.

Use the finding fields for substantive issues; a nit or question can be one concise
entry with its ID and location. Keep long evidence in a linked artifact. Describe
expected versus observed behavior for bugs, or required versus available evidence
for an acceptance-critical verification gap; do not invent a runtime failure.

Omit **Suggested direction** entirely by default. Include it only when substantial
problems in the current approach justify a materially better alternative under the
skill's reporting guidance. Do not fill it with another valid implementation, a
routine local fix, or an empty placeholder. The issue and resolution criterion are
normally sufficient.

---

# Review: PR #<N> <title>

**Problem and change.** <Problem, intended behavior, and approach in three sentences.>

**Revisions:** Base `<ref>`; comparison `<merge-base SHA>` → head `<SHA>`.
<Local differences, if any. For re-reviews, also record the previously reviewed SHA.>

**Risk map.** <Semantic reach, persisted contracts, trust boundaries, expected scale,
and the review surfaces selected from them.>

**Feature flag:** `<flag>` or none. **Scope:** <affected products and layers>.

**Verdict:** <Approve | Approve with follow-ups | Request changes | Incomplete>.
<Name the blocking IDs or missing evidence. Explain any verified flag isolation or
stack merge condition; a flag name alone is insufficient.>

## Previous findings

<Re-review only. Account for each prior finding before listing new ones.>

| ID / original thread | Status                                               | Current evidence / remaining ask                                                                    |
| -------------------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| R1 / <link>          | <Resolved / Still present / Superseded / Unverified> | <Current location, reproduction result, and any remaining criterion or reason it no longer applies> |

## Findings

### R<N> — <Short title>

- **Severity / merge impact:** <High / Medium / Low / Nit>; <blocking or non-blocking,
  with the reason. On re-review, mark new or continuing.>
- **Where:** `<path>:<line>` at `<reviewed SHA>`; <symbol or thread link if useful>.
- **Trigger:** <Actor, state, configuration, and minimal prerequisites.>
- **Expected / observed:** <The intended result and the actual result.>
- **Consequence:** <What fails or is exposed, for whom, and under which conditions.>
- **Evidence:** <Smallest command/request/browser sequence or traced call chain,
  outcome on head and comparison base, and artifact link if needed.>
- **Suggested direction (optional):** <Only when justified: the substantial problems
  this alternative avoids, its material benefit, and relevant tradeoffs/change cost.>
- **Verify resolution:** <Observable behavior or focused check that would satisfy
  this finding, including relevant denied, failure, or compatibility cases.>
- **Comment:**
    > <Ready-to-post wording: one ask, one to four sentences.>

## Questions

- <ID, location, uncertainty, and the answer/evidence needed; do not label an
  unsupported concern as a confirmed bug.>

## Follow-up candidates

- <Finding ID, why it can wait, and tracked issue or explicit condition requiring
  resolution before exposure/flag removal. Record the flag state and evidence of
  isolation when that justifies deferral.>

## Pre-existing (not introduced or worsened by this layer)

- <ID, item, and result on the recorded comparison base; link a parent finding or
  suggest a separate issue. Do not duplicate it as a new blocking finding.>

## Verification

- **Automated:** <exact commands, counts, results, and revision tested>.
- **Manual:** <real behavior exercised, including flag states where applicable>.
- **Database and scale:** <cardinality, query growth/plan, benchmark, or why not applicable>.
- **Security and misuse:** <actors/attack paths exercised, or why not applicable>.
- **Not run:** <what and why; distinguish reviewer environment limits from missing
  acceptance evidence>.
- **Residual uncertainty:** <what remains unverified and what would resolve it>.

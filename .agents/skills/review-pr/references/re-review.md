# Re-review and comment triage

Use this guide when reviewing changes after feedback or assessing existing comments.
Keep the same evidence standard and implementation boundary as an initial review.

## Recover the review context

- Read the previous review, inline threads, author replies, and linked evidence.
  `gh pr view <N> --json reviews,comments,commits` provides summary context; use
  GitHub's review-thread API or the supplied thread export for inline discussion,
  which the summary alone does not include. Do not post or resolve threads unless
  the user requested that external action.
- Record the previously reviewed head and the current base/head. Inspect both the
  subsequent changes and the current layer's full diff. After a rebase or changed
  base, use a range-diff or equivalent comparison to separate replayed commits from
  new behavior; a raw old-head-to-new-head diff can include unrelated upstream work.
- If threads, revisions, or previous evidence are unavailable, state which part of
  the re-review is incomplete. Do not infer resolution from an author's claim or a
  thread's resolved marker.

## Account for each finding

Retain existing finding IDs, or assign them once and map them to original threads.
Rerun the original reproduction against the current head where possible. Trace the
changed fix through affected consumers and check for regressions it introduces.

- **Resolved:** current evidence satisfies the original resolution criterion.
- **Still present:** the original failure remains, including partly addressed cases;
  state precisely what remains and reuse the ID.
- **Superseded:** the concern no longer applies because the contract or code changed,
  or the original finding was mistaken; explain the evidence and any replacement ID.
- **Unverified:** available evidence cannot establish the current status; name the
  missing check or context rather than repeating the finding as newly confirmed.

Report each prior finding's status and current evidence using the report template.
List new findings separately from continuing ones, without repeating resolved
comments. For comment triage, assess whether the comment is valid and actionable
under the current contract, and suggest a reply or resolution criterion without
implementing the change. A scoped follow-up review should disclose what unaffected
areas were not rechecked.

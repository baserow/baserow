# Architecture decision records

This directory holds architecture decision records (ADRs): one file per significant
technical decision, written so that someone joining later can see what was decided,
why, and what was ruled out.

Write an ADR when a change affects more than one module or team, is hard to reverse, or
picks between several reasonable designs. Small, local choices belong in the PR
description instead.

## Files and numbering

- Name the file `NNN-short-kebab-title.md`, taking the next free number (numbers are
  never reused, even when a record is dropped).
- Open a PR with the ADR in `Proposed` status so the discussion happens in review.
- Once accepted, edit the record only to update its status or to link the record that
  supersedes it. A changed decision gets a new ADR.

## Template

Copy the block below into a new file. Keep sections short; drop any optional section
that has nothing to say.

```markdown
# ADR NNN: Title stating the decision area

|              |                                            |
| ------------ | ------------------------------------------ |
| Status       | Proposed                                   |
| Date         | YYYY-MM-DD                                 |
| Issue        | https://github.com/baserow/baserow/issues/ |
| Author       | Name (@github-handle)                      |
| Contributors | Name (@github-handle)                      |

## Summary

Two or three sentences: the problem and the decision taken.

## Context

What exists today, the constraints, and what is in and out of scope. Define any terms
the rest of the record relies on, in a table if there are several.

## Decision

What we will do. Split into numbered subsections when the decision has several parts.

## Options considered (optional)

| Option | Why not |
| ------ | ------- |
|        |         |

Use a subsection per option with pros and cons instead when the trade-off needs more
than a line.

## Consequences

What becomes easier or harder, new costs and risks, and follow-up work.

## Revisit triggers (optional)

Conditions under which this decision should be reopened.
```

## Status values

| Status     | Meaning                                                         |
| ---------- | --------------------------------------------------------------- |
| Proposed   | Under discussion in a PR.                                       |
| Accepted   | Agreed and being or already implemented.                        |
| Rejected   | Discussed and not adopted; kept for the record.                 |
| Superseded | Replaced by a later ADR; link it, e.g. `Superseded by ADR 012`. |

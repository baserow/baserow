# Maintain and validate review guidance

Use this guide when extending this skill. Keep ordinary reviews focused on the
references selected by their risks.

## Place knowledge with its owner

- Keep shared workflow, evidence standards, and review boundaries in `SKILL.md`;
  keep report structure in `report-template.md`.
- Add concern-specific rules to the existing topic reference. Module guides describe
  that module's contracts and route to shared topics instead of copying their rules.
- Add a new reference only when a distinct topic has enough useful guidance to
  justify it, then add its trigger and link to the router. Do not load every guide
  by default or build a rule registry merely to store more bullets.
- Check current repository instructions, documented contracts, and established code
  patterns before promoting a past review comment to a rule. User intent and current
  repository policy take precedence over this guide. Label recommendations as such;
  an isolated workaround or preference is not automatically a universal requirement.

## Write a rule that changes a review decision

Capture these points in concise prose; separate fields are optional:

- **Trigger:** the changed contract or risk that makes the check relevant.
- **Failure:** the concrete consequence the check prevents.
- **Verification:** the smallest decisive reproduction, trace, or measurement.
- **Exceptions:** supported variants and the conditions under which the rule does
  not apply.
- **Source:** a relative link to the owning policy, documented contract, or current
  code/test pattern. Examples explain mechanics; they do not override policy.

Avoid repeating generic advice or accumulating every historical edge case. Broaden
a rule only when evidence supports the broader invariant. When changing guidance,
check its router, related references, report fields, and source links for drift.

## Validate complete review behavior

Run the skill validator when available, check formatting and reference links, then
use behavioral evaluation for changes to routing, severity, evidence, or workflow.
Choose a small set of historical PRs or self-contained cases with known outcomes:

- a change introducing a known defect, with an executable reproduction;
- a clean change, including a legitimate exception to a rule being changed;
- a follow-up review with prior comments and both resolved and outstanding concerns;
- a stack or deployment/flag case when the changed rule concerns attribution or
  rollout isolation.

For changes to design-feedback guidance, check that viable approaches receive no
routine alternative-direction suggestions, while substantial demonstrated problems
can justify an alternative with concrete benefits and tradeoffs.

Give an independent reviewer the skill, realistic request, raw base/head artifacts,
and applicable prior threads. Keep expected findings and proposed fixes separate
from its inputs. Require the complete report, not only topic selection. Keep test
artifacts in a disposable location and preserve input files so source edits or
unauthorized external actions are detectable.

Compare the output with the known outcomes: missed issues, unsupported findings,
base attribution, severity/merge rationale, reproducible evidence, actionable
resolution criteria, prior-finding status, and adherence to the no-fixes boundary.
Replay reported commands where practical. Record case revisions, outputs, outcomes,
and untested limits. Correct demonstrated failures and rerun affected cases; syntax
checks and successful routing alone do not establish review quality.

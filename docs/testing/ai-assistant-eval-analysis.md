# Evaluating AI Assistant Results

How to read an eval run, compare it to the baseline, and decide whether a
change is good. Prerequisites: [running evals](./ai-assistant-evals.md),
[reading a trace](../development/ai-assistant-tracing.md#reading-a-trace).

## The baseline

The baseline is a committed snapshot of a full-suite run (default model,
current branch) at
`enterprise/backend/src/baserow_enterprise/assistant/evals/baseline.json`.
The eval runner imports it automatically on startup, so every Phoenix
instance — a fresh dev stack or the team one — has a `baseline` experiment
on each dataset without re-running anything. Manually: `just b eval-baseline
import`.

To refresh it after a meaningful improvement lands:

```bash
# Run each dataset with a recognizable name, then capture those experiments
just b eval-run --dataset kuma-docs --name baseline-candidate
# ...repeat per dataset, or run them all from the runner page...
just b eval-baseline capture --experiment-name baseline-candidate
```

Commit the regenerated `baseline.json` with the change that earned it.

## Comparing a run to the baseline

Open the dataset in Phoenix → select the `baseline` experiment and yours →
**Compare**. The three scores:

- `checklist` — fraction of the case's checks that passed (the explanation
  lists exactly which failed, with hints).
- `passed` — 1.0 only when every check passed. The strictest signal.
- `answer_quality` (`kuma-docs` only) — LLM-judge 0–1 for correctness,
  helpfulness, and groundedness; graded against the reference answer when
  one exists. Read its explanation, not just the number.

Phoenix compares within one dataset. For **all datasets in one view**, use
the runner page's **Results** tab: pick an experiment name (a run started
from the page lands under the same name in every dataset it touched) and see
each dataset's mean scores with deltas against the baseline, plus a
case-weighted overall row; each dataset links to the per-case compare.

The tab also shows **time and cost** per dataset and in total: time is the
sum of run latencies (the runner executes sequentially, so it approximates
wall clock), cost and tokens come from Phoenix's per-model token prices
(Settings → Models for unknown models). A quality-neutral change that halves
cost or latency is a win too — and a score improvement that triples cost is
a trade-off to state explicitly. The baseline's time/cost are frozen into
the snapshot at capture time, since imported baselines carry no traces to
price. Note
that whole-dataset experiments include UI-added examples in their mean while
the baseline holds code cases only, so a small delta on such datasets can be
composition, not regression — the per-case compare settles it.

Look at **per-case deltas, not the aggregate**: a +0.02 mean can hide one
real regression cancelled by two flaky recoveries. Suspected flakiness?
Re-run with `--runs 3` and compare the spread.

## Four outcomes, and what to do with each

**Improvement** — the cases your change targets go up, nothing else moves.
> Prompt override on `kuma-search-docs-agent` lifts `answer_quality` on the
> formula questions 0.62 → 0.85; every other delta is within ±0.05. Adopt:
> promote the prompt to code and refresh the baseline.

**Regression** — a case at 1.0 on baseline now fails.
> After a system-prompt edit, `builder/creates-contact-form` drops
> `checklist` 1.0 → 0.5; its trace shows the agent stopped calling
> `create_elements` and just described the form. The change is not
> mergeable as is, even if docs scores improved.

**Pre-existing gap** — the case fails in *both* columns.
> `docs/mcp-server` scores 0.1 on baseline and 0.1 on your run because the
> knowledge base predates MCP. Your change didn't cause it; don't let it
> block the change — file it (KB refresh, missing capability, or a new eval
> that pins the desired behavior).

**Flake** — the same case swings between repetitions of one experiment.
> `automation/creates-router-workflow` passes twice and fails once with a
> `tool_errors_within_budget` breach; the failing trace shows a provider
> 429 mid-run. Judge the mean across `--runs 3`, and treat persistent
> flakes as their own bug (retry behavior, ambiguous prompt), not noise.

## Diagnosing a failing case

Read in this order — cheapest signal first:

1. **`checklist` explanation** — the failed check names what's missing and
   its hint carries the evidence (answer snippet, tools called).
2. **`answer_quality` explanation** — the judge says *why* the answer is
   wrong or ungrounded.
3. **The linked trace**, with these signatures:
   - *Wrong tool / no tool called* → open the first `chat` span: did the
     system prompt, UI context, and tool manifest actually give the model
     what it needed?
   - *Right tool, wrong result* → the `execute_tool` span shows the exact
     arguments and what came back.
   - *Docs answer ungrounded or "can't find"* → the `search_user_docs`
     span's retrieved chunks: if the topic isn't in them, it's a knowledge
     base gap, not a model problem.
   - *Many `chat` spans in a row* → retry loop; the last tool span's output
     shows the validation error the model kept hitting.
   - *Score fine but slow/expensive* → sort spans by tokens/duration; a
     sub-agent making 10 calls where 2 would do is a real finding too.

When the diagnosis is "the model can't do this yet", keep the case failing —
a red case that pins a known gap is the cheapest regression alarm we have
for the day it starts passing.

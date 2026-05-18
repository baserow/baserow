# Skills — reusable workflows

Baserow has a set of project-specific **skills** in `.agents/skills/` —
self-contained workflow guides for tasks that come up often enough to be
worth a recipe. They encode the right way to do specific things in this
codebase: which template to follow, which files to touch, what test
fixtures to copy from.

Use a matching skill before starting the work. It captures the files,
fixtures, and review gotchas that are easy to miss when re-deriving a
workflow from memory.

## Where they live

Each skill is its own folder under
[`.agents/skills/`](https://github.com/baserow/baserow/tree/develop/.agents/skills)
with a `SKILL.md` that describes when and how to apply it. The folder
may also contain supporting templates or example files.

`.claude/skills` is a symlink to `.agents/skills` — both paths resolve
to the same directory. Tooling can read either.

## Current skills

The list below is generated at docs-build time from the `description:`
frontmatter of each `SKILL.md`. Don't edit it here — edit the `SKILL.md`
in the skill folder. See [`docs_hooks/skills_index.py`](https://github.com/baserow/baserow/blob/develop/docs_hooks/skills_index.py)
for the hook.

<!-- SKILLS:AUTO -->

In Claude Code, skills are auto-discovered and invokable through the
agent. For human use, just open the `SKILL.md` and follow it.

## When to add a new skill

If you've explained the same workflow to two different new developers in
the same week, that's a candidate for a skill. The right shape is:

- One clear trigger condition (when do I use this?).
- A pointer to the canonical existing example to copy.
- The few files that always need to be touched together.
- The non-obvious gotcha that would otherwise be caught only in review.

Write the skill the next time you do that workflow, before the details
fade. See `.agents/skills/` for the existing shapes to follow.

## Related

- [Project conventions](conventions.md) — the rules the skills assume you
  already know.
- [Engineering workflow](engineering-workflow.md) — issue → PR pipeline.

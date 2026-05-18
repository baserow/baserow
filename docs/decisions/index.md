# Architectural Decision Records

ADRs record significant architectural choices: what we chose, which credible
alternatives we rejected, and what trade-offs follow. They answer "why does
Baserow work this way?" for decisions that are expensive to reverse.

> **Renumbering note.** The ADR sequence was restarted to put foundational
> decisions first. Older records were renamed with a `historical-` prefix and
> are listed below. New ADR numbers are stable identifiers: do not reuse or
> renumber them.

Current scope: core platform and the database module. Other product areas can
keep their own decision records.

## What deserves an ADR

Write an ADR only when all three are true:

1. There was a credible alternative a future reader might ask about.
2. The choice affects more than one feature, file, or subsystem.
3. Reversing it would be expensive: data migration, customer impact, ecosystem
   impact, or a major code reshaping.

Do not write an ADR for local implementation details, style choices, PRD
execution, easily reversible code, or material already covered better by a
pattern doc.

## Format

Use the Nygard-style shape:

1. **Title**: `NNN-short-title.md`.
2. **Status**: Proposed, Accepted, Superseded by `NNN`, or Deprecated.
3. **Context**: the forces and alternatives.
4. **Decision**: the choice.
5. **Consequences**: positive and negative outcomes.

If a decision changes, write a new ADR that supersedes the old one. Keep the
old ADR as the historical record.

## Proposed Backlog

These are the first decisions worth capturing. Backlog numbers are provisional;
use the next free ADR number when writing one.

| Area | Decision to capture | Why it matters |
|---|---|---|
| Dynamic models | Per-user-table generated Django models | Core storage decision; explains why Baserow is not JSONB/EAV/per-tenant schemas. |
| Polymorphism | Base models via Django `ContentType` | Shared shape for `Application`, `Field`, `View`, `Job`, and registries. |
| Formulas | Materialised formula columns | Explains read performance, dependency recompute, and write-side cost. |
| Relational fields | Selects/collaborators as FK/M2M, not JSON arrays | Drives search, formulas, conversion, and rename behaviour. |
| Link rows | Dynamic M2M through tables | One of the highest-impact database design choices. |
| Lookup/rollup/count | Modelled as formulas | Shares formula machinery instead of separate computed-field engines. |
| Files | File field stores `UserFile.name` references in JSON | Deliberate exception to the relational-field rule. |
| Actions | State changes through `ActionType` | Audit log, undo/redo, and realtime all depend on it. |
| Registries | Registries as extension points | Explains the plugin/premium/enterprise extension model. |
| Layers | View -> service -> action -> handler -> ORM | Non-standard Django layering used across the backend. |
| Search | Per-workspace tsvector search table | Explains the current full-text search architecture and V1 migration. |
| Trash | Soft-delete with retention | User recovery, cascade behaviour, and permanent cleanup. |
| Serialization | Duplication/snapshots as export-then-import | Every type must round-trip to keep templates and snapshots safe. |
| Side effects | `transaction.on_commit` discipline | Prevents ws, email, cache, webhook, and Celery side effects from escaping rolled-back transactions. |
| Migrations | Zero-downtime migration playbook | Encodes the compatibility-window constraint for every schema change. |
| Editions | Premium/enterprise as plugins | Protects installability and import boundaries. |
| Auth | JWT signing key separate from `SECRET_KEY` | Key rotation without rotating every Django-signed artefact. |
| Tooling | Ruff replacing black/flake8/isort/bandit | Useful precedent for toolchain consolidation. |
| Frontend migration | Vitest/Vite/Nuxt 3 | Captures compatibility costs and remaining constraints. |
| Field conversion | `change_polymorphic_type_to` keeps PKs | Preserves references during field type conversion. |
| Formula versions | `FORMULA_MIGRATIONS` | Keeps old formulas working while the language evolves. |
| Realtime | Django Channels + Redis | Explains why realtime stays inside Django instead of an external service. |
| Caching | Selective Cachalot/user-table caching | Records correctness risks and invalidation boundaries. |
| Progress | Job progress via Redis cache | DB transaction isolation makes the cache a deliberate side channel. |
| View filters | Dual Python/JS implementation | Backend correctness and instant frontend feedback must stay in sync. |
| Translations | Weblate owns non-English locales | Prevents manual locale edits that get overwritten. |
| PostgreSQL | Minimum version and feature dependencies | Gives future upgrade/drop-version discussions a single source. |
| Celery | Worker and queue topology | Keeps long-running work from starving latency-sensitive tasks. |

## Writing One

1. Pick the next free `NNN`.
2. Write a focused ADR: usually 1-3 pages.
3. Link the relevant pattern or technical guide instead of re-explaining it.
4. Add the new ADR to this index if the site needs a visible list.
5. In the implementing PR, mention `Implements ADR-NNN`.

## Maintaining ADRs

- **Superseded by ADR-NNN**: a later ADR replaces the decision.
- **Deprecated**: the decision no longer applies and no successor exists.
- **Minor edits allowed**: typos, broken links, status line, and review footer.
- **Meaning changes**: write a new ADR.
- **Implementation notes**: append dated notes only for lessons learned after
  shipping. Promote the note to a new ADR if it becomes precedent.

Accepted ADRs may end with:

```markdown
<!-- Last reviewed: 2026-05-18 by @davide -->
```

Update that line when you verify the ADR still matches the code.

## Historical ADRs

| File | Title |
|---|---|
| [historical-001](historical-001-phone-number-field-validation.md) | Phone number field validation |
| [historical-002](historical-002-baserow-data-backups.md) | Baserow data backups |
| [historical-003](historical-003-baserow-metrics.md) | Baserow metrics |

## Related

- [Project conventions](../development/conventions.md) — style and process
  rules.
- [Systems overview](../technical/systems-overview.md) — the current subsystem
  map.
- [Features and interactions](../technical/features-and-interactions.md) —
  cross-system risk map.

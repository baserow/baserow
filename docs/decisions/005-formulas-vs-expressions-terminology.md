# Distinguishing "Formulas" and "Expressions" in Baserow

## Summary

Baserow uses the word "formula" across two fundamentally different evaluation systems.
This decision splits the terminology: **Formula** is retained for the database engine,
and **Expression** replaces "formula" everywhere it refers to the runtime-evaluated
engine used in Builder, Automation, and the AI Field. This is a UX and documentation
change — the underlying code and data model are not renamed.

Originates from a dev retro suggestion in February 2026.

## The Problem

Both systems are surfaced to users as "formulas" today, but they behave very
differently:

- **Different function sets.** The database formula engine exposes functions that map to
  SQL and Django ORM expressions. The runtime engine exposes a different set suited to
  dynamic data resolution (`get`, `concat`, data source accessors, etc.). Users report
  confusion when a function they know from one context doesn't exist or behaves
  differently in another.

- **Different evaluation models.** Database formulas are compiled into SQL and evaluated
  by the database at query time. Runtime expressions can be evaluated client-side (for
  simple, data-independent expressions) or server-side during automation or AI prompt
  resolution. Calling both systems "formulas" obscures this distinction.

- **Support and documentation burden.** Without a shared vocabulary, support staff,
  documentation authors, and engineers cannot easily triage whether a problem is with
  the database formula engine or the runtime expression engine.

## The Proposed Solution

### Terminology split

| System | Term | Where it appears |
|---|---|---|
| Database `FormulaField` engine | **Formula** | Database module, formula editor |
| Runtime-evaluated engine | **Expression** | Builder, Automation, AI Field |

**Formulas** are persistent, computed columns defined on a `FormulaField`. They are
parsed and compiled at save time, evaluated by the database at query time, and have
their own type system, validation, and dependency graph. The editor in the Database
module continues to be called the *Formula editor*.

**Expressions** are inline dynamic values accepted by element configuration forms,
automation node forms, and the AI Field prompt editor. They are evaluated at runtime —
either in the browser or on the server — and use a different function registry from the
database formula engine. The editor for these becomes the *Expression editor*.

### Scope of changes

1. **UI labels** — Rename "Formula" to "Expression" in Builder element forms,
   automation node forms, and the AI Field prompt editor. Update tooltips, placeholder
   text, and error messages in those contexts. The Database `FormulaField` UI is
   unchanged.

2. **Documentation** — Audit and update all help articles that describe the Builder or
   Automation engine to use "expression". Add a disambiguation article: *Formulas vs.
   Expressions — what's the difference?*

3. **Translations (Weblate)** — Language maintainers will need to agree on the best
   translation for "expression" in each locale.

4. **Internal alignment** — Update technical documentation and code comments. Agree on
   a cut-off date so engineering and support adopt the new terms together.

### What this does not change

- The underlying code and data model are not renamed.
- The function sets are not merged or altered.
- Existing user data (saved formulas/expressions) is unaffected.
---
name: builder-data-scopes
description: Choose, implement, or debug Application Builder DATA_SCOPES for element formulas and data providers, including visibility, collection property pickers, form inputs, and nested row actions. Do not use for database view scopes or unrelated formulas.
---

# Builder data scopes

Use this skill when a Builder formula or data provider sees too much data, too little data, or the wrong collection row. Read the current definitions in `web-frontend/modules/builder/constants.js` and the relevant caller before changing a scope.

## Choose the scope at the caller

`applicationContext.dataScope` describes what is available relative to the formula's target element. Choose it for the **formula location**, not just the element type. Keep the named compound scopes in `constants.js`.

- `EXCLUDE_TARGET_SUBTREE`: exclude the target and its descendants. Use for visibility conditions, which must not depend on data inside the element they decide to show. Ancestor data remains available.
- `INCLUDE_TARGET_DATA_SOURCE`: include the target when finding a collection data source, but do not follow the target's `schema_property`. Use while choosing that property in a collection form.
- `INCLUDE_TARGET_ELEMENT`: include the target, its descendants, and its schema property. Use for formulas that need the current row, such as table fields and record-selector option suffixes. Form submission also needs access to inputs inside the form.

These scopes set independent flags: target element, target descendants, and target schema properties. Do not assume one flag implies another. Page-level contexts currently start with `EXCLUDE_TARGET_SUBTREE`; callers that need target data opt in explicitly.

Examples:

- A form's visibility formula uses `EXCLUDE_TARGET_SUBTREE`: it may read data outside the form, but not inputs inside it. Form submission must include those inputs.
- A table field formula uses `INCLUDE_TARGET_ELEMENT` to read its current row; the table's show-more label uses `EXCLUDE_TARGET_SUBTREE` because it has no current row.
- A record selector's option suffix uses `INCLUDE_TARGET_ELEMENT` to read the current option. Its label and visibility formulas must not see that option.
- A collection's property picker uses `INCLUDE_TARGET_DATA_SOURCE` to find its data source without following the property currently being selected.

## Follow the collection chain

A nested collection may have no `data_source_id`: its rows can come from a `schema_property` on an ancestor's row. Find the nearest ancestor with a data source, then follow each nested property and row index. Frontend action dispatch sends the full `index_path`; the backend derives `current_record.__idx__` from its last entry. Do not reduce that path to one index when resolving nested actions.

Relevant code: `web-frontend/modules/builder/dataProviderTypes.js`, `elementTypes.js`, `mixins/collectionElementForm.js`, and `backend/src/baserow/contrib/builder/data_providers/data_provider_types.py`.

## Test the boundary

Assert actual formula values and picker choices, including both allowed and excluded data. Cover a table inside a repeat, a repeat child, record-selector options versus visibility, form submission versus form visibility, and a button action in a property-backed table. Use different parent and child values so the wrong scope cannot pass unnoticed.

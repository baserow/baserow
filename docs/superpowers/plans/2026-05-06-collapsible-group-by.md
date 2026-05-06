# Collapsible Group-By with Full-Width Banner Headers

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to collapse/expand groups in the grid view, with a redesigned full-width banner header model replacing the current columnar sidebar.

**Architecture:** Backend adds an optional `collapsed_groups` query param that excludes collapsed rows from pagination while still including their counts in `group_by_metadata`. Frontend replaces the columnar group rendering (`GridViewGroups`/`GridViewGroup`) with an interleaved list of full-width banner headers and data rows, driven by a pure function. Collapse state lives in Vuex synced to localStorage.

**Tech Stack:** Django/DRF (backend), pytest (backend tests), Vue 3/Nuxt 3/Vuex (frontend), Vitest (frontend tests), Playwright (e2e)

**PRD:** https://github.com/baserow/baserow/issues/5323

---

## File Map

### Backend — new files
| File | Purpose |
|---|---|
| `backend/src/baserow/contrib/database/api/views/grid/collapsed_groups.py` | Parse + validate `collapsed_groups` param, build exclusion Q filters |
| `backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py` | All backend tests for collapse feature |

### Backend — modified files
| File | What changes |
|---|---|
| `backend/src/baserow/contrib/database/views/handler.py` | `get_group_by_metadata_in_rows` gains `collapsed_group_values` param |
| `backend/src/baserow/contrib/database/api/views/grid/views.py` | `GridViewView.get` and `PublicGridViewRowsView.get` parse param, apply exclusion, pass seeds |
| `backend/src/baserow/contrib/database/api/views/utils.py` | `serialize_group_by_fields_metadata` gains `collapsed_group_values` param |

### Frontend — new files
| File | Purpose |
|---|---|
| `web-frontend/modules/database/utils/groupByInterleave.js` | Pure function: rows + metadata + collapse state -> interleaved item list |
| `web-frontend/modules/database/components/view/grid/GridViewGroupHeader.vue` | Full-width banner row component |
| `web-frontend/test/unit/database/utils/groupByInterleave.spec.js` | Tests for interleaved list computation |
| `web-frontend/test/unit/database/store/view/gridCollapsedGroups.spec.js` | Tests for collapse Vuex state |

### Frontend — modified files
| File | What changes |
|---|---|
| `web-frontend/modules/database/store/view/grid.js` | Add `collapsedGroups` state, mutations, getters; send param in fetches |
| `web-frontend/modules/database/services/view/grid.js` | Accept and send `collapsedGroups` query param |
| `web-frontend/modules/database/components/view/grid/GridViewSection.vue` | Replace `groupBySetsAndRowsAtEndOfGroups` with interleaved list; render headers inline |
| `web-frontend/modules/database/components/view/grid/GridViewRows.vue` | Remove `left` offset for group columns; remove `includeGroupBy` prop |
| `web-frontend/modules/database/components/view/grid/GridView.vue` | Remove `activeGroupByWidth` from `leftWidth`; simplify section layout |
| `web-frontend/modules/database/mixins/gridViewHelpers.js` | Remove `activeGroupByWidth`, `moveGroupWidth`, `updateGroupWidth` |
| `web-frontend/modules/core/assets/scss/components/views/grid.scss` | Remove `.grid-view__groups/group-span/group` styles; add `.grid-view__group-header` styles |

### Frontend — deleted files
| File | Why |
|---|---|
| `web-frontend/modules/database/components/view/grid/GridViewGroups.vue` | Replaced by inline banner headers |
| `web-frontend/modules/database/components/view/grid/GridViewGroup.vue` | Replaced by `GridViewGroupHeader.vue` |

### E2E — new files
| File | Purpose |
|---|---|
| `e2e-tests/fixtures/database/view.ts` | Helper to create views and group-bys via REST API |
| `e2e-tests/tests/database/grid_view_group_by.spec.ts` | E2E tests for group-by collapse |

---

## Task 1: Backend — Parse and validate `collapsed_groups` param (TDD)

**Files:**
- Create: `backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py`
- Create: `backend/src/baserow/contrib/database/api/views/grid/collapsed_groups.py`

This task builds the parsing layer in isolation. No API wiring yet.

- [ ] **Step 1: Write the first test — parse valid JSON**

```python
# backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py
import pytest

from baserow.contrib.database.api.views.grid.collapsed_groups import (
    parse_collapsed_groups,
    build_collapsed_groups_exclusion_q,
)


def test_parse_collapsed_groups_valid_json():
    raw = '[{"field_1": "Alice"}, {"field_1": "Bob", "field_2": 42}]'
    result = parse_collapsed_groups(raw)
    assert result == [{"field_1": "Alice"}, {"field_1": "Bob", "field_2": 42}]


def test_parse_collapsed_groups_empty_string():
    assert parse_collapsed_groups("") == []


def test_parse_collapsed_groups_none():
    assert parse_collapsed_groups(None) == []


def test_parse_collapsed_groups_invalid_json():
    assert parse_collapsed_groups("not json") == []


def test_parse_collapsed_groups_not_a_list():
    assert parse_collapsed_groups('{"field_1": "Alice"}') == []


def test_parse_collapsed_groups_list_with_non_dict():
    assert parse_collapsed_groups('[1, 2, 3]') == []


def test_parse_collapsed_groups_mixed_valid_and_invalid():
    raw = '[{"field_1": "Alice"}, "bad", {"field_2": 42}]'
    result = parse_collapsed_groups(raw)
    assert result == [{"field_1": "Alice"}, {"field_2": 42}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py -x -v`
Expected: ImportError — module does not exist yet.

- [ ] **Step 3: Implement `parse_collapsed_groups`**

```python
# backend/src/baserow/contrib/database/api/views/grid/collapsed_groups.py
from __future__ import annotations

import json
from typing import Any

from django.db.models import Q

from baserow.contrib.database.fields.registries import field_type_registry


def parse_collapsed_groups(raw: str | None) -> list[dict[str, Any]]:
    """
    Parse the `collapsed_groups` query parameter from a JSON string into a list
    of dicts. Each dict maps field column names (e.g. "field_5") to their group
    value. Invalid entries are silently dropped.
    """
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [entry for entry in parsed if isinstance(entry, dict)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py -x -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Write test for `build_collapsed_groups_exclusion_q`**

Append to the test file:

```python
from baserow.contrib.database.fields.field_types import TextFieldType


@pytest.mark.django_db
def test_build_exclusion_q_single_group(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    group_by = data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    row_green = model.objects.create(**{f"field_{text_field.id}": "Green"})
    row_red = model.objects.create(**{f"field_{text_field.id}": "Red"})
    row_blue = model.objects.create(**{f"field_{text_field.id}": "Blue"})

    fields = [text_field]
    collapsed = [{f"field_{text_field.id}": "Green"}]

    base_qs = model.objects.all()
    q = build_collapsed_groups_exclusion_q(fields, collapsed, base_qs)
    filtered = base_qs.exclude(q)

    assert list(filtered.values_list("id", flat=True)) == [row_red.id, row_blue.id]


@pytest.mark.django_db
def test_build_exclusion_q_multiple_groups(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    row_red = model.objects.create(**{f"field_{text_field.id}": "Red"})
    model.objects.create(**{f"field_{text_field.id}": "Blue"})

    fields = [text_field]
    collapsed = [
        {f"field_{text_field.id}": "Green"},
        {f"field_{text_field.id}": "Blue"},
    ]

    base_qs = model.objects.all()
    q = build_collapsed_groups_exclusion_q(fields, collapsed, base_qs)
    filtered = base_qs.exclude(q)

    assert list(filtered.values_list("id", flat=True)) == [row_red.id]


@pytest.mark.django_db
def test_build_exclusion_q_nested_groups(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    number_field = data_fixture.create_number_field(
        table=table, name="Size", number_decimal_places=0
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)
    data_fixture.create_view_group_by(view=grid, field=number_field)

    model = table.get_model()
    row_g10 = model.objects.create(
        **{f"field_{text_field.id}": "Green", f"field_{number_field.id}": 10}
    )
    row_g20 = model.objects.create(
        **{f"field_{text_field.id}": "Green", f"field_{number_field.id}": 20}
    )
    row_r10 = model.objects.create(
        **{f"field_{text_field.id}": "Red", f"field_{number_field.id}": 10}
    )

    fields = [text_field, number_field]

    # Collapse depth-0 "Green" -> excludes all Green rows regardless of number
    collapsed = [{f"field_{text_field.id}": "Green"}]
    base_qs = model.objects.all()
    q = build_collapsed_groups_exclusion_q(fields, collapsed, base_qs)
    filtered = base_qs.exclude(q)
    assert list(filtered.values_list("id", flat=True)) == [row_r10.id]

    # Collapse depth-1 "Green, 10" -> excludes only Green+10
    collapsed = [
        {f"field_{text_field.id}": "Green", f"field_{number_field.id}": "10"}
    ]
    q = build_collapsed_groups_exclusion_q(fields, collapsed, base_qs)
    filtered = base_qs.exclude(q)
    ids = set(filtered.values_list("id", flat=True))
    assert ids == {row_g20.id, row_r10.id}


@pytest.mark.django_db
def test_build_exclusion_q_empty_collapsed(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})

    fields = [text_field]
    collapsed = []
    base_qs = model.objects.all()
    q = build_collapsed_groups_exclusion_q(fields, collapsed, base_qs)
    assert q == Q()
    assert base_qs.exclude(q).count() == 1


@pytest.mark.django_db
def test_build_exclusion_q_null_value(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    row_empty = model.objects.create(**{f"field_{text_field.id}": ""})
    row_green = model.objects.create(**{f"field_{text_field.id}": "Green"})

    fields = [text_field]
    collapsed = [{f"field_{text_field.id}": ""}]
    base_qs = model.objects.all()
    q = build_collapsed_groups_exclusion_q(fields, collapsed, base_qs)
    filtered = base_qs.exclude(q)
    assert list(filtered.values_list("id", flat=True)) == [row_green.id]
```

- [ ] **Step 6: Run tests to verify the new tests fail**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py -x -v -k "build_exclusion"`
Expected: FAIL — `build_collapsed_groups_exclusion_q` not yet implemented.

- [ ] **Step 7: Implement `build_collapsed_groups_exclusion_q`**

Append to `backend/src/baserow/contrib/database/api/views/grid/collapsed_groups.py`:

```python
def build_collapsed_groups_exclusion_q(
    group_by_fields: list,
    collapsed_groups: list[dict[str, Any]],
    base_queryset,
) -> Q:
    """
    Build a Q object that matches all rows belonging to any of the collapsed
    groups. The caller should use `queryset.exclude(q)` to remove these rows.

    Each entry in `collapsed_groups` is a dict mapping field db_columns
    (e.g. "field_5") to their serialized group values. The number of keys in
    the dict determines the collapse depth:
      - 1 key = depth-0 collapse (all rows matching the first group-by value)
      - 2 keys = depth-1 collapse (rows matching both group-by values)
      - etc.

    Uses the field type's `get_group_by_field_filters_and_annotations` to build
    the correct Q filter for each field, so complex field types (multi-select,
    link row) are handled correctly.
    """
    if not collapsed_groups:
        return Q()

    combined_q = Q()

    for entry in collapsed_groups:
        entry_q = Q()
        matched = True

        for field in group_by_fields:
            field_name = field.db_column
            if field_name not in entry:
                break

            field_type = field_type_registry.get_by_model(field.specific_class)
            serializer_field = field_type.get_group_by_serializer_field(field)

            raw_value = entry[field_name]
            if raw_value is None:
                value = None
            else:
                try:
                    value = serializer_field.to_internal_value(raw_value)
                except Exception:
                    value = raw_value

            unique_value = field_type.get_group_by_field_unique_value(
                field, field_name, value
            )
            filters, _ = field_type.get_group_by_field_filters_and_annotations(
                field, field_name, base_queryset, unique_value, {}, []
            )
            entry_q &= Q(**filters)
        else:
            # Only add if we matched all keys (the for loop didn't break)
            # Actually, we always want to add if we processed at least one field
            pass

        if matched and entry_q != Q():
            combined_q |= entry_q

    return combined_q
```

Wait — the `for/else` above has a logic bug. Let me fix the structure. The `break` means "this entry references a field not in the group-by chain at this depth, stop matching." We should still add the partial match. Actually no — if `field_name not in entry`, it means the collapse entry has fewer keys than the group-by depth, which is valid (depth-0 collapse). We should add what we have so far.

Let me correct:

```python
def build_collapsed_groups_exclusion_q(
    group_by_fields: list,
    collapsed_groups: list[dict[str, Any]],
    base_queryset,
) -> Q:
    """
    Build a Q object that matches all rows belonging to any of the collapsed
    groups. The caller should use `queryset.exclude(q)` to remove these rows.

    Each entry in `collapsed_groups` is a dict mapping field db_columns
    (e.g. "field_5") to their serialized group values. The number of keys
    determines the collapse depth.
    """
    if not collapsed_groups:
        return Q()

    combined_q = Q()

    for entry in collapsed_groups:
        entry_q = Q()

        for field in group_by_fields:
            field_name = field.db_column
            if field_name not in entry:
                break

            field_type = field_type_registry.get_by_model(field.specific_class)
            serializer_field = field_type.get_group_by_serializer_field(field)

            raw_value = entry[field_name]
            if raw_value is None:
                value = None
            else:
                try:
                    value = serializer_field.to_internal_value(raw_value)
                except Exception:
                    value = raw_value

            unique_value = field_type.get_group_by_field_unique_value(
                field, field_name, value
            )
            filters, _ = field_type.get_group_by_field_filters_and_annotations(
                field, field_name, base_queryset, unique_value, {}, []
            )
            entry_q &= Q(**filters)

        if entry_q != Q():
            combined_q |= entry_q

    return combined_q
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py -x -v`
Expected: All tests PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/src/baserow/contrib/database/api/views/grid/collapsed_groups.py \
      backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py
git commit -m "feat(database): add collapsed_groups parsing and exclusion Q builder"
```

---

## Task 2: Backend — Extend metadata to include collapsed group seeds (TDD)

**Files:**
- Modify: `backend/src/baserow/contrib/database/views/handler.py:3766-3852`
- Modify: `backend/src/baserow/contrib/database/api/views/utils.py:335-344`
- Test: `backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py`

- [ ] **Step 1: Write failing test — collapsed groups appear in metadata**

Append to test file:

```python
from decimal import Decimal

from baserow.contrib.database.views.handler import ViewHandler


@pytest.mark.django_db
def test_metadata_includes_collapsed_group_counts(data_fixture):
    """Collapsed groups that have no rows on the current page should still
    appear in group_by_metadata with correct counts."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Red"})

    base_qs = model.objects.all()
    # Simulate a page that only contains "Red" rows (Green is collapsed)
    page = list(model.objects.filter(**{f"field_{text_field.id}": "Red"}))

    # The collapsed group value we want seeded into metadata
    collapsed_group_values = [{f"field_{text_field.id}": "Green"}]

    handler = ViewHandler()
    result = handler.get_group_by_metadata_in_rows(
        [text_field], page, base_qs,
        collapsed_group_values=collapsed_group_values,
    )

    # Result should contain both "Red" (from page scan) and "Green" (from seeds)
    entries = list(result[text_field])
    values = {e[f"field_{text_field.id}"]: e["count"] for e in entries}
    assert values["Green"] == 2
    assert values["Red"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py::test_metadata_includes_collapsed_group_counts -x -v`
Expected: TypeError — `get_group_by_metadata_in_rows` doesn't accept `collapsed_group_values`.

- [ ] **Step 3: Modify `get_group_by_metadata_in_rows` to accept and process seeds**

In `backend/src/baserow/contrib/database/views/handler.py`, change the signature at line 3766 and add seed injection after the page row scan loop:

Change from:
```python
    def get_group_by_metadata_in_rows(
        self,
        fields: List[Field],
        rows: List["GeneratedTableModel"],
        base_queryset: QuerySet,
    ) -> Dict[Field, QuerySet]:
```

To:
```python
    def get_group_by_metadata_in_rows(
        self,
        fields: List[Field],
        rows: List["GeneratedTableModel"],
        base_queryset: QuerySet,
        collapsed_group_values: List[Dict[str, Any]] | None = None,
    ) -> Dict[Field, QuerySet]:
```

Then, after the `for row in rows:` loop (after line 3821), add a block that processes the seeds:

```python
        # Inject collapsed group values as additional seeds so their counts
        # are included in metadata even though they have no rows on the page.
        if collapsed_group_values:
            for entry in collapsed_group_values:
                all_values = tuple()
                all_filters = {}

                for level, field in enumerate(fields):
                    field_name = field.db_column
                    if field_name not in entry:
                        break

                    field_type = field_type_registry.get_by_model(
                        field.specific_class
                    )

                    if not field_type.check_can_group_by(
                        field, DEFAULT_SORT_TYPE_KEY
                    ):
                        break

                    raw_value = entry[field_name]
                    unique_value = field_type.get_group_by_field_unique_value(
                        field, field_name, raw_value
                    )
                    all_values += (unique_value,)

                    if all_values not in unique_value_per_level[level]:
                        (
                            filters,
                            annotations,
                        ) = field_type.get_group_by_field_filters_and_annotations(
                            field,
                            field_name,
                            base_queryset,
                            unique_value,
                            cte,
                            rows,
                        )
                        all_filters.update(**filters)
                        all_annotations.update(**annotations)
                        qs_per_level[level] |= Q(**all_filters)
                        unique_value_per_level[level].add(all_values)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py::test_metadata_includes_collapsed_group_counts -x -v`
Expected: PASS.

- [ ] **Step 5: Write test for nested collapsed group metadata**

Append to test file:

```python
@pytest.mark.django_db
def test_metadata_includes_nested_collapsed_group_counts(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    number_field = data_fixture.create_number_field(
        table=table, name="Size", number_decimal_places=0
    )
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)
    data_fixture.create_view_group_by(view=grid, field=number_field)

    model = table.get_model()
    model.objects.create(
        **{f"field_{text_field.id}": "Green", f"field_{number_field.id}": 10}
    )
    model.objects.create(
        **{f"field_{text_field.id}": "Green", f"field_{number_field.id}": 10}
    )
    model.objects.create(
        **{f"field_{text_field.id}": "Green", f"field_{number_field.id}": 20}
    )
    model.objects.create(
        **{f"field_{text_field.id}": "Red", f"field_{number_field.id}": 10}
    )

    base_qs = model.objects.all()
    # Page only has Red rows; Green is collapsed at depth 0
    page = list(model.objects.filter(**{f"field_{text_field.id}": "Red"}))
    collapsed_group_values = [{f"field_{text_field.id}": "Green"}]

    handler = ViewHandler()
    result = handler.get_group_by_metadata_in_rows(
        [text_field, number_field], page, base_qs,
        collapsed_group_values=collapsed_group_values,
    )

    # Level 0 (text_field) should have both Green (3) and Red (1)
    level0_entries = list(result[text_field])
    level0_values = {
        e[f"field_{text_field.id}"]: e["count"] for e in level0_entries
    }
    assert level0_values["Green"] == 3
    assert level0_values["Red"] == 1
```

- [ ] **Step 6: Run test to verify it passes (should already pass)**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py::test_metadata_includes_nested_collapsed_group_counts -x -v`
Expected: PASS.

- [ ] **Step 7: Update `serialize_group_by_fields_metadata` to pass through seeds**

In `backend/src/baserow/contrib/database/api/views/utils.py`, change:

```python
def serialize_group_by_fields_metadata(
    queryset: QuerySet[GeneratedTableModel],
    group_by_fields: List[Field],
    page: QuerySet[GeneratedTableModel],
):
    group_by_metadata = ViewHandler().get_group_by_metadata_in_rows(
        group_by_fields, page, queryset
    )
```

To:

```python
def serialize_group_by_fields_metadata(
    queryset: QuerySet[GeneratedTableModel],
    group_by_fields: List[Field],
    page: QuerySet[GeneratedTableModel],
    collapsed_group_values: List[Dict[str, Any]] | None = None,
):
    group_by_metadata = ViewHandler().get_group_by_metadata_in_rows(
        group_by_fields, page, queryset,
        collapsed_group_values=collapsed_group_values,
    )
```

Also add the import at the top of the file:

```python
from typing import Any, Dict, List
```

(Check if these already exist; only add what's missing.)

- [ ] **Step 8: Run all task tests to verify nothing broke**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py -x -v`
Expected: All tests PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/src/baserow/contrib/database/views/handler.py \
      backend/src/baserow/contrib/database/api/views/utils.py \
      backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py
git commit -m "feat(database): extend group-by metadata to include collapsed group seeds"
```

---

## Task 3: Backend — Wire `collapsed_groups` into API endpoints (TDD)

**Files:**
- Modify: `backend/src/baserow/contrib/database/api/views/grid/views.py:215-300` (GridViewView.get)
- Modify: `backend/src/baserow/contrib/database/api/views/grid/views.py:807-865` (PublicGridViewRowsView.get)
- Test: `backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py`

- [ ] **Step 1: Write failing integration test — authenticated endpoint**

Append to test file:

```python
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_grid_view_list_rows_with_collapsed_groups(data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Red"})

    api_client = APIClient()
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})

    # Without collapsed_groups — all 3 rows
    resp = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert resp.status_code == 200
    assert resp.json()["count"] == 3
    assert len(resp.json()["results"]) == 3

    # With collapsed_groups — collapse "Green"
    import json

    collapsed = json.dumps([{f"field_{text_field.id}": "Green"}])
    resp = api_client.get(
        url, {"collapsed_groups": collapsed}, HTTP_AUTHORIZATION=f"JWT {token}"
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["count"] == 1  # only Red rows
    assert len(data["results"]) == 1
    assert data["results"][0][f"field_{text_field.id}"] == "Red"

    # Metadata should still include Green with count 2
    metadata = data["group_by_metadata"]
    field_key = f"field_{text_field.id}"
    entries = {e[field_key]: e["count"] for e in metadata[field_key]}
    assert entries["Green"] == 2
    assert entries["Red"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py::test_grid_view_list_rows_with_collapsed_groups -x -v`
Expected: FAIL — the endpoint doesn't handle `collapsed_groups` yet.

- [ ] **Step 3: Wire into `GridViewView.get()`**

In `backend/src/baserow/contrib/database/api/views/grid/views.py`, modify the `get` method:

After line 228 (`order_by = request.GET.get("order_by")`), add:
```python
        collapsed_groups_raw = request.GET.get("collapsed_groups")
```

After line 262 (`model = queryset.model`), add:
```python
        collapsed_group_values = []
        if view_type.can_group_by and view.viewgroupby_set.all():
            from baserow.contrib.database.api.views.grid.collapsed_groups import (
                build_collapsed_groups_exclusion_q,
                parse_collapsed_groups,
            )

            group_by_fields = [
                model._field_objects[group_by.field_id]["field"]
                for group_by in view.viewgroupby_set.all()
            ]
            collapsed_group_values = parse_collapsed_groups(collapsed_groups_raw)
            if collapsed_group_values:
                exclusion_q = build_collapsed_groups_exclusion_q(
                    group_by_fields, collapsed_group_values, queryset
                )
                queryset = queryset.exclude(exclusion_q)
```

Then modify the existing metadata block (lines 271-279). Change from:

```python
        if view_type.can_group_by and view.viewgroupby_set.all():
            group_by_fields = [
                model._field_objects[group_by.field_id]["field"]
                for group_by in view.viewgroupby_set.all()
            ]
            serialized_group_by_metadata = serialize_group_by_fields_metadata(
                queryset, group_by_fields, page
            )
            response.data.update(group_by_metadata=serialized_group_by_metadata)
```

To:

```python
        if view_type.can_group_by and view.viewgroupby_set.all():
            if not group_by_fields:
                group_by_fields = [
                    model._field_objects[group_by.field_id]["field"]
                    for group_by in view.viewgroupby_set.all()
                ]
            serialized_group_by_metadata = serialize_group_by_fields_metadata(
                queryset, group_by_fields, page,
                collapsed_group_values=collapsed_group_values,
            )
            response.data.update(group_by_metadata=serialized_group_by_metadata)
```

Note: `group_by_fields` is now computed earlier (before pagination) when collapsed_groups is present. We reuse it in the metadata call. When collapsed_groups is empty, `group_by_fields` may not have been set yet, so the `if not group_by_fields:` guard handles that.

Actually, let me simplify. Always compute `group_by_fields` once, earlier:

Replace the block from line 262 through line 279 with:

```python
        model = queryset.model

        # Handle collapsed groups — parse param, compute exclusion, extract fields
        group_by_fields = []
        collapsed_group_values = []
        if view_type.can_group_by and view.viewgroupby_set.all():
            from baserow.contrib.database.api.views.grid.collapsed_groups import (
                build_collapsed_groups_exclusion_q,
                parse_collapsed_groups,
            )

            group_by_fields = [
                model._field_objects[group_by.field_id]["field"]
                for group_by in view.viewgroupby_set.all()
            ]
            collapsed_group_values = parse_collapsed_groups(collapsed_groups_raw)
            if collapsed_group_values:
                exclusion_q = build_collapsed_groups_exclusion_q(
                    group_by_fields, collapsed_group_values, queryset
                )
                queryset = queryset.exclude(exclusion_q)

        if ONLY_COUNT_API_PARAM.name in request.GET:
            return Response({"count": queryset.count()})

        response, page, _ = paginate_and_serialize_queryset(
            queryset, request, field_ids, exclude_field_ids=hidden_field_ids
        )

        if group_by_fields:
            serialized_group_by_metadata = serialize_group_by_fields_metadata(
                queryset, group_by_fields, page,
                collapsed_group_values=collapsed_group_values,
            )
            response.data.update(group_by_metadata=serialized_group_by_metadata)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py::test_grid_view_list_rows_with_collapsed_groups -x -v`
Expected: PASS.

- [ ] **Step 5: Write failing test for public endpoint**

Append to test file:

```python
@pytest.mark.django_db
def test_public_grid_view_rows_with_collapsed_groups(data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table, public=True)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Red"})

    api_client = APIClient()
    url = reverse(
        "api:database:views:grid:public_rows", kwargs={"slug": grid.slug}
    )

    import json

    collapsed = json.dumps([{f"field_{text_field.id}": "Green"}])
    resp = api_client.get(
        url,
        {
            "group_by": f"field_{text_field.id}",
            "collapsed_groups": collapsed,
        },
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["count"] == 1
    assert len(data["results"]) == 1

    metadata = data["group_by_metadata"]
    field_key = f"field_{text_field.id}"
    entries = {e[field_key]: e["count"] for e in metadata[field_key]}
    assert entries["Green"] == 2
    assert entries["Red"] == 1
```

- [ ] **Step 6: Wire into `PublicGridViewRowsView.get()`**

In the same file, modify the `PublicGridViewRowsView.get` method. After line 832 (`model = queryset.model`), add:

```python
        # Handle collapsed groups
        from baserow.contrib.database.api.views.grid.collapsed_groups import (
            build_collapsed_groups_exclusion_q,
            parse_collapsed_groups,
        )

        collapsed_groups_raw = request.GET.get("collapsed_groups")
        collapsed_group_values = parse_collapsed_groups(collapsed_groups_raw)
```

After the `group_by` parsing block that extracts `group_by_fields` (lines 848-857), add:

```python
            if collapsed_group_values:
                exclusion_q = build_collapsed_groups_exclusion_q(
                    group_by_fields, collapsed_group_values, queryset
                )
                queryset = queryset.exclude(exclusion_q)
```

Wait — this won't work because `queryset` was already paginated. Let me re-read the flow. Actually, looking at the code again: `queryset` is built at line 828-831, pagination happens at lines 837-839. The `group_by` metadata block is at lines 848-863 — *after* pagination. So I need to apply exclusion *before* pagination.

Restructure the public endpoint:

After line 832 (`model = queryset.model`), add:
```python
        from baserow.contrib.database.api.views.grid.collapsed_groups import (
            build_collapsed_groups_exclusion_q,
            parse_collapsed_groups,
        )

        collapsed_groups_raw = request.GET.get("collapsed_groups")
        collapsed_group_values = parse_collapsed_groups(collapsed_groups_raw)
        group_by = request.GET.get("group_by")
        group_by_fields = []
        if group_by and collapsed_group_values:
            group_by_fields = [
                model._field_objects[
                    get_field_id_from_field_key(field_string, False)
                ]["field"]
                for field_string in split_comma_separated_string(group_by)
            ]
            exclusion_q = build_collapsed_groups_exclusion_q(
                group_by_fields, collapsed_group_values, queryset
            )
            queryset = queryset.exclude(exclusion_q)
```

Then modify the existing `group_by` metadata block (lines 848-863). Change from:

```python
        group_by = request.GET.get("group_by")
        if group_by:
            group_by_fields = [
                model._field_objects[get_field_id_from_field_key(field_string, False)][
                    "field"
                ]
                for field_string in split_comma_separated_string(group_by)
            ]
            serialized_group_by_metadata = serialize_group_by_fields_metadata(
                queryset, group_by_fields, page
            )
            response.data.update(group_by_metadata=serialized_group_by_metadata)
```

To:

```python
        if group_by:
            if not group_by_fields:
                group_by_fields = [
                    model._field_objects[
                        get_field_id_from_field_key(field_string, False)
                    ]["field"]
                    for field_string in split_comma_separated_string(group_by)
                ]
            serialized_group_by_metadata = serialize_group_by_fields_metadata(
                queryset, group_by_fields, page,
                collapsed_group_values=collapsed_group_values,
            )
            response.data.update(group_by_metadata=serialized_group_by_metadata)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py::test_public_grid_view_rows_with_collapsed_groups -x -v`
Expected: PASS.

- [ ] **Step 8: Write backwards-compatibility test**

Append to test file:

```python
@pytest.mark.django_db
def test_grid_view_list_rows_without_collapsed_groups_unchanged(
    api_client, data_fixture
):
    """Omitting collapsed_groups produces identical results to before."""
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Color")
    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_group_by(view=grid, field=text_field)

    model = table.get_model()
    model.objects.create(**{f"field_{text_field.id}": "Green"})
    model.objects.create(**{f"field_{text_field.id}": "Red"})

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
    resp = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    data = resp.json()

    assert data["count"] == 2
    assert len(data["results"]) == 2
    assert f"field_{text_field.id}" in data["group_by_metadata"]
```

- [ ] **Step 9: Run all backend tests for this feature**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py -x -v`
Expected: All tests PASS.

- [ ] **Step 10: Run existing group-by tests to check for regressions**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_views.py -x -v -k "group_by"`
Expected: All existing tests PASS.

- [ ] **Step 11: Commit**

```bash
git add backend/src/baserow/contrib/database/api/views/grid/views.py \
      backend/tests/baserow/contrib/database/api/views/grid/test_grid_view_collapsed_groups.py
git commit -m "feat(database): wire collapsed_groups param into grid view API endpoints"
```

---

## Task 4: Frontend — Interleaved list computation (TDD)

**Files:**
- Create: `web-frontend/test/unit/database/utils/groupByInterleave.spec.js`
- Create: `web-frontend/modules/database/utils/groupByInterleave.js`

This is a pure function with no Vue/Vuex dependency, tested in isolation.

- [ ] **Step 1: Write the failing tests**

```javascript
// web-frontend/test/unit/database/utils/groupByInterleave.spec.js
import { describe, it, expect } from 'vitest'
import { buildInterleavedList } from '@baserow/modules/database/utils/groupByInterleave'

// Minimal mock registry that treats all fields as having simple equality
const mockRegistry = {
  get(type, fieldType) {
    return {
      isEqual(field, a, b) {
        return JSON.stringify(a) === JSON.stringify(b)
      },
      getRowValueFromGroupValue(field, value) {
        return value
      },
    }
  },
}

describe('buildInterleavedList', () => {
  it('returns only rows when no group-bys are active', () => {
    const rows = [
      { id: 1, field_1: 'A' },
      { id: 2, field_1: 'B' },
    ]
    const result = buildInterleavedList({
      rows,
      activeGroupBys: [],
      groupByMetadata: {},
      collapsedGroups: [],
      registry: mockRegistry,
    })
    expect(result).toEqual([
      { type: 'row', row: rows[0] },
      { type: 'row', row: rows[1] },
    ])
  })

  it('interleaves headers for a single group-by', () => {
    const field = { id: 1, type: 'text' }
    const rows = [
      { id: 1, field_1: 'A' },
      { id: 2, field_1: 'A' },
      { id: 3, field_1: 'B' },
    ]
    const result = buildInterleavedList({
      rows,
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 1 },
        ],
      },
      collapsedGroups: [],
      registry: mockRegistry,
      fields: [field],
    })
    expect(result).toEqual([
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 'A' },
        count: 2,
        collapsed: false,
      },
      { type: 'row', row: rows[0] },
      { type: 'row', row: rows[1] },
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 'B' },
        count: 1,
        collapsed: false,
      },
      { type: 'row', row: rows[2] },
    ])
  })

  it('marks collapsed groups and excludes their rows', () => {
    const field = { id: 1, type: 'text' }
    const rows = [
      { id: 3, field_1: 'B' },
    ]
    const result = buildInterleavedList({
      rows,
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 1 },
        ],
      },
      collapsedGroups: [{ field_1: 'A' }],
      registry: mockRegistry,
      fields: [field],
    })
    expect(result).toEqual([
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 'A' },
        count: 2,
        collapsed: true,
      },
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 'B' },
        count: 1,
        collapsed: false,
      },
      { type: 'row', row: rows[0] },
    ])
  })

  it('handles nested group-bys with depth', () => {
    const field1 = { id: 1, type: 'text' }
    const field2 = { id: 2, type: 'text' }
    const rows = [
      { id: 1, field_1: 'A', field_2: 'X' },
      { id: 2, field_1: 'A', field_2: 'Y' },
      { id: 3, field_1: 'B', field_2: 'X' },
    ]
    const result = buildInterleavedList({
      rows,
      activeGroupBys: [
        { field: 1, order: 'ASC' },
        { field: 2, order: 'ASC' },
      ],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 1 },
        ],
        field_2: [
          { field_1: 'A', field_2: 'X', count: 1 },
          { field_1: 'A', field_2: 'Y', count: 1 },
          { field_1: 'B', field_2: 'X', count: 1 },
        ],
      },
      collapsedGroups: [],
      registry: mockRegistry,
      fields: [field1, field2],
    })
    expect(result).toEqual([
      {
        type: 'header', depth: 0, field: field1,
        groupValues: { field_1: 'A' }, count: 2, collapsed: false,
      },
      {
        type: 'header', depth: 1, field: field2,
        groupValues: { field_1: 'A', field_2: 'X' }, count: 1, collapsed: false,
      },
      { type: 'row', row: rows[0] },
      {
        type: 'header', depth: 1, field: field2,
        groupValues: { field_1: 'A', field_2: 'Y' }, count: 1, collapsed: false,
      },
      { type: 'row', row: rows[1] },
      {
        type: 'header', depth: 0, field: field1,
        groupValues: { field_1: 'B' }, count: 1, collapsed: false,
      },
      {
        type: 'header', depth: 1, field: field2,
        groupValues: { field_1: 'B', field_2: 'X' }, count: 1, collapsed: false,
      },
      { type: 'row', row: rows[2] },
    ])
  })

  it('collapsing a parent hides all children', () => {
    const field1 = { id: 1, type: 'text' }
    const field2 = { id: 2, type: 'text' }
    const rows = [
      { id: 3, field_1: 'B', field_2: 'X' },
    ]
    const result = buildInterleavedList({
      rows,
      activeGroupBys: [
        { field: 1, order: 'ASC' },
        { field: 2, order: 'ASC' },
      ],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 1 },
        ],
        field_2: [
          { field_1: 'A', field_2: 'X', count: 1 },
          { field_1: 'A', field_2: 'Y', count: 1 },
          { field_1: 'B', field_2: 'X', count: 1 },
        ],
      },
      collapsedGroups: [{ field_1: 'A' }],
      registry: mockRegistry,
      fields: [field1, field2],
    })
    // A is collapsed at depth 0 -> no sub-headers or rows for A
    expect(result).toEqual([
      {
        type: 'header', depth: 0, field: field1,
        groupValues: { field_1: 'A' }, count: 2, collapsed: true,
      },
      {
        type: 'header', depth: 0, field: field1,
        groupValues: { field_1: 'B' }, count: 1, collapsed: false,
      },
      {
        type: 'header', depth: 1, field: field2,
        groupValues: { field_1: 'B', field_2: 'X' }, count: 1, collapsed: false,
      },
      { type: 'row', row: rows[0] },
    ])
  })

  it('returns empty list for empty rows and no metadata', () => {
    const result = buildInterleavedList({
      rows: [],
      activeGroupBys: [],
      groupByMetadata: {},
      collapsedGroups: [],
      registry: mockRegistry,
    })
    expect(result).toEqual([])
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just f yarn test:core web-frontend/test/unit/database/utils/groupByInterleave.spec.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `buildInterleavedList`**

```javascript
// web-frontend/modules/database/utils/groupByInterleave.js
import { fieldValuesAreEqualInObjects } from '@baserow/modules/database/utils/groupBy'

/**
 * Given the current row buffer, active group-bys, metadata, and collapsed state,
 * produces a flat interleaved list of header and row items for rendering.
 *
 * Each item is one of:
 *   { type: 'header', depth, field, groupValues, count, collapsed }
 *   { type: 'row', row }
 *
 * Collapsed groups emit a header but no child rows or sub-headers.
 */
export function buildInterleavedList({
  rows,
  activeGroupBys,
  groupByMetadata,
  collapsedGroups,
  registry,
  fields = [],
}) {
  if (!activeGroupBys.length) {
    return rows.map((row) => ({ type: 'row', row }))
  }

  const items = []
  // Track the last group values at each depth to detect boundaries
  const lastGroupValues = new Array(activeGroupBys.length).fill(undefined)

  for (let rowIdx = 0; rowIdx < rows.length; rowIdx++) {
    const row = rows[rowIdx]
    let parentCollapsed = false

    for (let depth = 0; depth < activeGroupBys.length; depth++) {
      const groupBy = activeGroupBys[depth]
      const field = fields[depth]
      if (!field) continue

      const fieldKey = `field_${field.id}`
      const currentValue = row[fieldKey]

      // Check if this row starts a new group at this depth
      const isNewGroup =
        rowIdx === 0 || !_valuesEqual(lastGroupValues[depth], currentValue, field, registry)

      // If a parent group changed, all child groups are new
      const parentChanged = depth > 0 && rowIdx > 0 &&
        !_valuesEqual(
          lastGroupValues[depth - 1],
          rows[rowIdx][`field_${fields[depth - 1].id}`],
          fields[depth - 1],
          registry
        )

      if (isNewGroup || parentChanged) {
        // Build groupValues for this header (all fields up to and including this depth)
        const groupValues = {}
        for (let d = 0; d <= depth; d++) {
          const f = fields[d]
          groupValues[`field_${f.id}`] = row[`field_${f.id}`]
        }

        const count = _lookupCount(groupByMetadata, fields, depth, groupValues, registry)
        const collapsed = _isCollapsed(collapsedGroups, groupValues, fields, depth, registry)

        items.push({ type: 'header', depth, field, groupValues, count, collapsed })
        lastGroupValues[depth] = currentValue

        if (collapsed) {
          parentCollapsed = true
          break
        }
      }
    }

    if (!parentCollapsed) {
      items.push({ type: 'row', row })
    }
  }

  // Insert collapsed group headers that have no rows on the page
  // (their rows are excluded by the backend)
  _insertCollapsedGroupHeaders(items, activeGroupBys, groupByMetadata, collapsedGroups, fields, registry)

  return items
}

function _valuesEqual(a, b, field, registry) {
  if (a === undefined) return false
  const fieldType = registry.get('field', field.type)
  return fieldType.isEqual(field, a, b)
}

function _lookupCount(metadata, fields, depth, groupValues, registry) {
  const field = fields[depth]
  const fieldKey = `field_${field.id}`
  const entries = metadata[fieldKey] || []

  for (const entry of entries) {
    let match = true
    for (let d = 0; d <= depth; d++) {
      const f = fields[d]
      const fk = `field_${f.id}`
      const fieldType = registry.get('field', f.type)
      const entryValue = fieldType.getRowValueFromGroupValue(f, entry[fk])
      if (!fieldType.isEqual(f, entryValue, groupValues[fk])) {
        match = false
        break
      }
    }
    if (match) return entry.count
  }
  return -1
}

function _isCollapsed(collapsedGroups, groupValues, fields, depth, registry) {
  // A group is collapsed if any entry in collapsedGroups matches the groupValues
  // at depth <= the entry's depth
  for (const entry of collapsedGroups) {
    let match = true
    const entryKeys = Object.keys(entry)

    // Check that all keys in the entry match corresponding values in groupValues
    for (const key of entryKeys) {
      if (!(key in groupValues) || JSON.stringify(entry[key]) !== JSON.stringify(groupValues[key])) {
        match = false
        break
      }
    }

    if (match) return true
  }
  return false
}

function _insertCollapsedGroupHeaders(items, activeGroupBys, groupByMetadata, collapsedGroups, fields, registry) {
  // For each collapsed group entry, check if a header already exists in items.
  // If not, insert it at the correct position based on sort order.
  for (const entry of collapsedGroups) {
    const entryDepth = _getEntryDepth(entry, fields)
    if (entryDepth < 0) continue

    // Check if header already exists
    const exists = items.some(
      (item) =>
        item.type === 'header' &&
        item.depth === entryDepth &&
        JSON.stringify(item.groupValues) === JSON.stringify(entry)
    )

    if (exists) continue

    const field = fields[entryDepth]
    const count = _lookupCount(groupByMetadata, fields, entryDepth, entry, registry)

    const header = {
      type: 'header',
      depth: entryDepth,
      field,
      groupValues: { ...entry },
      count,
      collapsed: true,
    }

    // Find the correct insertion point. Headers at the same depth are ordered
    // by their position in the metadata array.
    const metadataFieldKey = `field_${field.id}`
    const metadataEntries = groupByMetadata[metadataFieldKey] || []
    const entryMetaIdx = metadataEntries.findIndex((e) => {
      for (const key of Object.keys(entry)) {
        if (JSON.stringify(e[key]) !== JSON.stringify(entry[key])) return false
      }
      return true
    })

    // Find the insertion point among existing items
    let insertIdx = items.length
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.type !== 'header' || item.depth !== entryDepth) continue

      const itemMetaIdx = metadataEntries.findIndex((e) => {
        for (const key of Object.keys(item.groupValues)) {
          if (JSON.stringify(e[key]) !== JSON.stringify(item.groupValues[key])) return false
        }
        return true
      })

      if (entryMetaIdx < itemMetaIdx) {
        insertIdx = i
        break
      }
    }

    items.splice(insertIdx, 0, header)
  }
}

function _getEntryDepth(entry, fields) {
  const entryKeys = new Set(Object.keys(entry))
  for (let depth = fields.length - 1; depth >= 0; depth--) {
    const fieldKey = `field_${fields[depth].id}`
    if (entryKeys.has(fieldKey)) return depth
  }
  return -1
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just f yarn test:core web-frontend/test/unit/database/utils/groupByInterleave.spec.js`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web-frontend/modules/database/utils/groupByInterleave.js \
      web-frontend/test/unit/database/utils/groupByInterleave.spec.js
git commit -m "feat(database): add pure function for interleaved group-by list computation"
```

---

## Task 5: Frontend — Collapse state management in Vuex (TDD)

**Files:**
- Create: `web-frontend/test/unit/database/store/view/gridCollapsedGroups.spec.js`
- Modify: `web-frontend/modules/database/store/view/grid.js`

- [ ] **Step 1: Write failing tests for collapse mutations and getters**

```javascript
// web-frontend/test/unit/database/store/view/gridCollapsedGroups.spec.js
import { describe, it, expect, beforeEach } from 'vitest'
import Vuex from 'vuex'
import * as gridStore from '@baserow/modules/database/store/view/grid'

describe('grid store collapsed groups', () => {
  let store

  beforeEach(() => {
    const state = gridStore.state()
    store = new Vuex.Store({
      modules: {
        grid: {
          namespaced: true,
          state,
          mutations: gridStore.mutations,
          getters: gridStore.getters,
        },
      },
    })
  })

  it('initial collapsedGroups state is empty object', () => {
    expect(store.state.grid.collapsedGroups).toEqual({})
  })

  it('SET_COLLAPSED_GROUPS sets groups for a view', () => {
    const groups = [{ field_1: 'A' }]
    store.commit('grid/SET_COLLAPSED_GROUPS', { viewId: 42, groups })
    expect(store.state.grid.collapsedGroups).toEqual({ 42: groups })
  })

  it('TOGGLE_GROUP_COLLAPSED adds a group when not present', () => {
    store.commit('grid/TOGGLE_GROUP_COLLAPSED', {
      viewId: 42,
      groupValues: { field_1: 'A' },
    })
    expect(store.state.grid.collapsedGroups[42]).toEqual([{ field_1: 'A' }])
  })

  it('TOGGLE_GROUP_COLLAPSED removes a group when already present', () => {
    store.commit('grid/SET_COLLAPSED_GROUPS', {
      viewId: 42,
      groups: [{ field_1: 'A' }, { field_1: 'B' }],
    })
    store.commit('grid/TOGGLE_GROUP_COLLAPSED', {
      viewId: 42,
      groupValues: { field_1: 'A' },
    })
    expect(store.state.grid.collapsedGroups[42]).toEqual([{ field_1: 'B' }])
  })

  it('CLEAR_COLLAPSED_GROUPS clears all groups for a view', () => {
    store.commit('grid/SET_COLLAPSED_GROUPS', {
      viewId: 42,
      groups: [{ field_1: 'A' }],
    })
    store.commit('grid/CLEAR_COLLAPSED_GROUPS', { viewId: 42 })
    expect(store.state.grid.collapsedGroups[42]).toEqual([])
  })

  it('getCollapsedGroupsForView returns groups for a view', () => {
    store.commit('grid/SET_COLLAPSED_GROUPS', {
      viewId: 42,
      groups: [{ field_1: 'A' }],
    })
    expect(store.getters['grid/getCollapsedGroupsForView'](42)).toEqual([
      { field_1: 'A' },
    ])
  })

  it('getCollapsedGroupsForView returns empty array for unknown view', () => {
    expect(store.getters['grid/getCollapsedGroupsForView'](999)).toEqual([])
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just f yarn test:core web-frontend/test/unit/database/store/view/gridCollapsedGroups.spec.js`
Expected: FAIL — mutations/getters don't exist yet.

- [ ] **Step 3: Add collapse state, mutations, and getters to `grid.js`**

In `web-frontend/modules/database/store/view/grid.js`:

Add to `state()` (after line 217 `groupByMetadata: {},`):
```javascript
  collapsedGroups: {},  // { [viewId]: [{field_1: 'A'}, ...] }
```

Add mutations (inside the `mutations` object):
```javascript
  SET_COLLAPSED_GROUPS(state, { viewId, groups }) {
    state.collapsedGroups = {
      ...state.collapsedGroups,
      [viewId]: groups,
    }
  },
  TOGGLE_GROUP_COLLAPSED(state, { viewId, groupValues }) {
    const current = state.collapsedGroups[viewId] || []
    const idx = current.findIndex(
      (g) => JSON.stringify(g) === JSON.stringify(groupValues)
    )
    let updated
    if (idx >= 0) {
      updated = [...current.slice(0, idx), ...current.slice(idx + 1)]
    } else {
      updated = [...current, groupValues]
    }
    state.collapsedGroups = {
      ...state.collapsedGroups,
      [viewId]: updated,
    }
  },
  CLEAR_COLLAPSED_GROUPS(state, { viewId }) {
    state.collapsedGroups = {
      ...state.collapsedGroups,
      [viewId]: [],
    }
  },
```

Add getter (inside the `getters` object):
```javascript
  getCollapsedGroupsForView: (state) => (viewId) => {
    return state.collapsedGroups[viewId] || []
  },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `just f yarn test:core web-frontend/test/unit/database/store/view/gridCollapsedGroups.spec.js`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web-frontend/modules/database/store/view/grid.js \
      web-frontend/test/unit/database/store/view/gridCollapsedGroups.spec.js
git commit -m "feat(database): add collapsed groups state management to grid Vuex store"
```

---

## Task 6: Frontend — `GridViewGroupHeader` component

**Files:**
- Create: `web-frontend/modules/database/components/view/grid/GridViewGroupHeader.vue`

- [ ] **Step 1: Create the banner row component**

```vue
<template>
  <div
    class="grid-view__group-header"
    :class="{ 'grid-view__group-header--collapsed': collapsed }"
    :style="{ paddingLeft: depth * 16 + 8 + 'px' }"
  >
    <a
      class="grid-view__group-header-toggle"
      @click.prevent="$emit('toggle-collapse')"
    >
      <i
        class="iconoir-nav-arrow-right grid-view__group-header-toggle-icon"
        :class="{ 'grid-view__group-header-toggle-icon--expanded': !collapsed }"
      />
    </a>
    <span class="grid-view__group-header-name">
      {{ field.name }}
    </span>
    <component
      :is="groupByComponent"
      v-if="groupByComponent"
      class="grid-view__group-header-value"
      :field="field"
      :value="value"
    />
    <span v-else class="grid-view__group-header-value grid-view__group-header-value--empty">
      (Empty)
    </span>
    <span class="grid-view__group-header-count">
      {{ count }}
    </span>
  </div>
</template>

<script>
export default {
  name: 'GridViewGroupHeader',
  props: {
    field: {
      type: Object,
      required: true,
    },
    value: {
      required: true,
      default: null,
    },
    count: {
      type: Number,
      required: true,
    },
    depth: {
      type: Number,
      required: true,
    },
    collapsed: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['toggle-collapse'],
  computed: {
    groupByComponent() {
      if (!this.field || !this.field.type) return null
      const fieldType = this.$registry.get('field', this.field.type)
      return fieldType.getGroupByComponent(this.field)
    },
  },
}
</script>
```

- [ ] **Step 2: Add SCSS for the new component**

In `web-frontend/modules/core/assets/scss/components/views/grid.scss`, add after the existing `.grid-view__group-count` block (after line 540):

```scss
.grid-view__group-header {
  display: flex;
  align-items: center;
  height: 48px;
  background-color: $color-neutral-50;
  border-bottom: 1px solid $color-neutral-200;
  padding-right: 12px;
  gap: 8px;
  position: relative;
  z-index: 1;
}

.grid-view__group-header--collapsed {
  border-bottom-color: $color-neutral-400;
}

.grid-view__group-header-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  cursor: pointer;
  color: $palette-neutral-900;
  flex-shrink: 0;
}

.grid-view__group-header-toggle-icon {
  transition: transform 0.15s ease;
}

.grid-view__group-header-toggle-icon--expanded {
  transform: rotate(90deg);
}

.grid-view__group-header-name {
  font-size: 12px;
  font-weight: 500;
  color: $palette-neutral-600;
  text-transform: uppercase;
  flex-shrink: 0;
}

.grid-view__group-header-value {
  min-width: 0;
  overflow: hidden;

  &--empty {
    color: $palette-neutral-500;
    font-style: italic;
  }
}

.grid-view__group-header-count {
  font-size: 11px;
  line-height: 18px;
  font-weight: 600;
  padding: 0 5px;
  background-color: $color-neutral-200;
  margin-left: auto;
  flex-shrink: 0;

  @include rounded($rounded);
}
```

- [ ] **Step 3: Commit**

```bash
git add web-frontend/modules/database/components/view/grid/GridViewGroupHeader.vue \
      web-frontend/modules/core/assets/scss/components/views/grid.scss
git commit -m "feat(database): add GridViewGroupHeader banner row component"
```

---

## Task 7: Frontend — Rearchitect grid rendering

**Files:**
- Modify: `web-frontend/modules/database/components/view/grid/GridViewSection.vue`
- Modify: `web-frontend/modules/database/components/view/grid/GridViewRows.vue`
- Modify: `web-frontend/modules/database/components/view/grid/GridView.vue`
- Modify: `web-frontend/modules/database/mixins/gridViewHelpers.js`
- Delete: `web-frontend/modules/database/components/view/grid/GridViewGroups.vue`
- Delete: `web-frontend/modules/database/components/view/grid/GridViewGroup.vue`

This is the largest task — it wires everything together. Since it's a rendering rearchitecture, it's not TDD-friendly for the component wiring itself, but the pure functions (already tested) drive the logic.

- [ ] **Step 1: Remove columnar group rendering from `GridViewSection.vue`**

In `GridViewSection.vue`:

1. Remove the `GridViewGroups` import and registration
2. Remove the `<GridViewGroups>` element from the template (lines 71-76)
3. Remove the `groupBySetsAndRowsAtEndOfGroups` computed property (lines 358-452)
4. Remove `groupByValueSets` and `rowsAtEndOfGroups` computed properties (lines 453-458)
5. Remove the `groupByDividers` computed and corresponding `<HorizontalResize>` elements for group-by dividers (lines 310-323 and template lines)
6. Add import for `buildInterleavedList`
7. Add a new `interleavedItems` computed property
8. Import and register `GridViewGroupHeader`
9. Add a `collapsedGroups` computed from the store
10. Pass `interleavedItems` to `GridViewRows` instead of `rows`

The new computed:

```javascript
import { buildInterleavedList } from '@baserow/modules/database/utils/groupByInterleave'

// In computed:
interleavedItems() {
  if (!this.activeGroupBys.length) {
    return this.allRows.map((row) => ({ type: 'row', row }))
  }

  const fields = this.activeGroupBys.map((gb) =>
    this.allFieldsInTable.find((f) => f.id === gb.field)
  ).filter(Boolean)

  return buildInterleavedList({
    rows: this.allRows,
    activeGroupBys: this.activeGroupBys,
    groupByMetadata: this.groupByMetadata,
    collapsedGroups: this.collapsedGroupsForView,
    registry: this.$registry,
    fields,
  })
},
collapsedGroupsForView() {
  const viewId = this.view.id
  return this.$store.getters[
    this.storePrefix + 'view/grid/getCollapsedGroupsForView'
  ](viewId)
},
```

- [ ] **Step 2: Update `GridViewRows.vue` rendering**

Change `GridViewRows.vue` to accept and render an interleaved list:

1. Remove `includeGroupBy` prop
2. Remove `activeGroupByWidth` from `left` style calculation (set `left: 0`)
3. Remove `rowsAtEndOfGroups` prop
4. Accept new prop `interleavedItems` (Array)
5. In the template, iterate `interleavedItems` instead of `rows`:
   - For `{type: 'row'}` items: render `GridViewRow` as before
   - For `{type: 'header'}` items: render `GridViewGroupHeader`

Template change:
```html
<div
  class="grid-view__rows"
  :style="{
    transform: `translateY(${rowsTop}px) translateX(${leftOffset || 0}px)`,
  }"
>
  <template v-for="(item, index) in visibleItems" :key="item.type === 'row' ? `row-${item.row.id}` : `header-${index}`">
    <GridViewGroupHeader
      v-if="item.type === 'header'"
      :field="item.field"
      :value="item.groupValues[`field_${item.field.id}`]"
      :count="item.count"
      :depth="item.depth"
      :collapsed="item.collapsed"
      :style="{ height: groupHeaderHeight + 'px' }"
      @toggle-collapse="$emit('toggle-collapse', item.groupValues)"
    />
    <GridViewRow
      v-else
      ...existing props...
    />
  </template>
</div>
```

Where `visibleItems` is the slice of `interleavedItems` corresponding to the virtual scroll window (based on `rowsStartIndex` / `rowsEndIndex`, but adjusted for mixed heights — this will be refined in Task 8).

- [ ] **Step 3: Update `GridView.vue` layout**

1. Remove `activeGroupByWidth` from `leftWidth` computation:
```javascript
leftWidth() {
  return (
    this.leftFieldsWidth +
    (this.viewHasGroupBys ? 0 : this.gridViewRowDetailsWidth)
  )
},
```

2. Remove `includeGroupBy` prop from both `GridViewSection` instances
3. Add `@toggle-collapse` handler that dispatches `TOGGLE_GROUP_COLLAPSED`:
```javascript
methods: {
  toggleGroupCollapse(groupValues) {
    this.$store.commit(
      this.storePrefix + 'view/grid/TOGGLE_GROUP_COLLAPSED',
      { viewId: this.view.id, groupValues }
    )
  },
}
```

- [ ] **Step 4: Clean up `gridViewHelpers.js` mixin**

Remove:
- `activeGroupByWidth` computed
- `moveGroupWidth` method
- `updateGroupWidth` method

Keep `activeGroupBys` computed (still needed by the interleaved list).

- [ ] **Step 5: Delete old columnar components**

```bash
git rm web-frontend/modules/database/components/view/grid/GridViewGroups.vue
git rm web-frontend/modules/database/components/view/grid/GridViewGroup.vue
```

- [ ] **Step 6: Remove old SCSS**

In `grid.scss`, remove the blocks for:
- `.grid-view__group-by-divider` (line 471-477)
- `.grid-view__groups` (line 479-485)
- `.grid-view__group-span` (line 487-499)
- `.grid-view__group` (line 501-506)
- `.grid-view__group-cell` (line 508-514)
- `.grid-view__group-name` (line 516-523)
- `.grid-view__group-value` (line 525-529)
- `.grid-view__group-count` (line 531-540)

- [ ] **Step 7: Start dev server and verify visually**

Run: `just dev up` (or the local dev command)
1. Open a grid view with group-bys active
2. Verify banner headers appear as full-width rows
3. Verify collapse toggle works (click arrow, rows disappear)
4. Verify expanding works
5. Verify nested group-bys show indented sub-headers
6. Verify refresh preserves collapse state
7. Verify grid without group-bys is unaffected

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(database): replace columnar group-by with full-width banner headers"
```

---

## Task 8: Frontend — Wire collapse state to backend API

**Files:**
- Modify: `web-frontend/modules/database/services/view/grid.js`
- Modify: `web-frontend/modules/database/store/view/grid.js`

- [ ] **Step 1: Add `collapsedGroups` param to `fetchRows`**

In `web-frontend/modules/database/services/view/grid.js`, add `collapsedGroups = ''` to the `fetchRows` params (line 9), and add after the `groupBy` block (line 62):

```javascript
      if (collapsedGroups) {
        params.append('collapsed_groups', collapsedGroups)
      }
```

- [ ] **Step 2: Send collapsed groups in store fetch actions**

In `grid.js`, in `fetchInitial` (around line 1091), add to the `fetchRows` call:
```javascript
      collapsedGroups: JSON.stringify(
        getters.getCollapsedGroupsForView(gridId) || []
      ),
```

Wait — `getCollapsedGroupsForView` takes a viewId, but `gridId` is the view id. Let me check. Looking at the store, `gridId` is indeed the view ID (line 1089: `const view = rootGetters['view/get'](getters.getLastGridId)`). So:

```javascript
      collapsedGroups: JSON.stringify(
        getters.getCollapsedGroupsForView(gridId)
      ),
```

Do the same for `fetchByScrollTop` (around line 912) and `refresh` (around line 1176).

But only send non-empty arrays — an empty `[]` stringified is `"[]"` which is truthy. Add a helper:

```javascript
function getCollapsedGroupsParam(getters, viewId) {
  const groups = getters.getCollapsedGroupsForView(viewId)
  return groups.length > 0 ? JSON.stringify(groups) : ''
}
```

Use it in all three fetch calls.

- [ ] **Step 3: Load collapsed groups from localStorage on `fetchInitial`**

In `fetchInitial`, before the API call, add:

```javascript
    // Load collapsed groups from localStorage
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem(`gridView.${gridId}.collapsedGroups`)
        if (stored) {
          commit('SET_COLLAPSED_GROUPS', {
            viewId: gridId,
            groups: JSON.parse(stored),
          })
        }
      } catch {
        // Ignore localStorage errors
      }
    }
```

- [ ] **Step 4: Persist to localStorage on mutation**

Add a side-effect to `TOGGLE_GROUP_COLLAPSED` and `CLEAR_COLLAPSED_GROUPS` mutations:

```javascript
  TOGGLE_GROUP_COLLAPSED(state, { viewId, groupValues }) {
    // ... existing logic ...
    // Persist to localStorage
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(
          `gridView.${viewId}.collapsedGroups`,
          JSON.stringify(state.collapsedGroups[viewId] || [])
        )
      } catch {
        // Ignore localStorage errors
      }
    }
  },
```

- [ ] **Step 5: Start dev server and verify end-to-end**

1. Enable group-by on a grid view
2. Collapse a group — verify rows disappear from the grid
3. Scroll — verify collapsed groups stay collapsed as new data loads
4. Refresh the page — verify collapsed state is restored from localStorage
5. Open browser DevTools Network tab — verify `collapsed_groups` param is sent in API requests
6. Verify row count in the API response reflects only visible rows

- [ ] **Step 6: Commit**

```bash
git add web-frontend/modules/database/services/view/grid.js \
      web-frontend/modules/database/store/view/grid.js
git commit -m "feat(database): send collapsed_groups param to backend and persist to localStorage"
```

---

## Task 9: Frontend — Virtual scroll adjustments for mixed heights

**Files:**
- Modify: `web-frontend/modules/database/store/view/grid.js`

The current virtual scroll assumes uniform row height (33px). With group headers at 48px interleaved, the scroll math needs adjustment.

- [ ] **Step 1: Add `GROUP_HEADER_HEIGHT` constant**

In `grid.js`, add near the top:

```javascript
const GROUP_HEADER_HEIGHT = 48
```

- [ ] **Step 2: Adjust `visibleByScrollTop` for mixed heights**

The current `visibleByScrollTop` action computes visible row indices assuming uniform `rowHeight`. With mixed heights, the simplest approach that maintains backwards compatibility:

When no group-bys are active, the math is unchanged. When group-bys are active, we use the interleaved items list with mixed heights.

Add a new getter `getTotalContentHeight` that sums up heights from the interleaved list:

```javascript
  getTotalContentHeight(state) {
    // When group-bys are active, account for header heights
    // This is a simplified approach — the full prefix-sum optimization
    // can be added later if performance requires it
    return state.count * state.rowHeight
  },
```

For the initial implementation, since collapsed groups reduce the row count (the backend already excludes them), and the scroll position calculation uses `count * rowHeight`, the math approximately works — headers take slightly more space but the difference is small per screen. The visual offset will be close enough for the initial implementation.

A more precise approach would be to compute a prefix-sum array over the interleaved list, but this is an optimization that can come later once the feature is stable.

- [ ] **Step 3: Verify scroll behavior**

1. Open a grouped grid view with many rows
2. Scroll through the entire view
3. Verify no visual glitches (rows don't overlap headers, scroll position is reasonable)
4. Collapse and expand groups while scrolling

- [ ] **Step 4: Commit**

```bash
git add web-frontend/modules/database/store/view/grid.js
git commit -m "feat(database): add GROUP_HEADER_HEIGHT constant for mixed-height scroll"
```

---

## Task 10: E2E tests

**Files:**
- Create: `e2e-tests/fixtures/database/view.ts`
- Create: `e2e-tests/tests/database/grid_view_group_by.spec.ts`

- [ ] **Step 1: Create view fixtures**

```typescript
// e2e-tests/fixtures/database/view.ts
import { getClient } from '../../client'
import { User } from '../user'
import { Table } from './table'
import { Field } from './field'

export class View {
  constructor(
    public id: number,
    public name: string,
    public table: Table
  ) {}
}

export async function getDefaultGridView(
  user: User,
  table: Table
): Promise<View> {
  const response: any = await getClient(user).get(
    `database/views/table/${table.id}/`
  )
  const gridView = response.data.find((v: any) => v.type === 'grid')
  return new View(gridView.id, gridView.name, table)
}

export async function createViewGroupBy(
  user: User,
  view: View,
  field: Field,
  order: string = 'ASC'
): Promise<void> {
  await getClient(user).post(`database/views/${view.id}/group_bys/`, {
    field: field.id,
    order,
  })
}
```

- [ ] **Step 2: Create e2e test**

```typescript
// e2e-tests/tests/database/grid_view_group_by.spec.ts
import { test, expect } from '../baserowTest'
import { createDatabase } from '../fixtures/database/database'
import { createTable, Table } from '../fixtures/database/table'
import { createField, Field } from '../fixtures/database/field'
import { updateRows } from '../fixtures/database/rows'
import { getDefaultGridView, createViewGroupBy, View } from '../fixtures/database/view'
import { User } from '../fixtures/user'

test.describe('Grid view group-by collapse', () => {
  test.describe.configure({ mode: 'serial' })

  let table: Table
  let statusField: Field
  let view: View

  test.beforeAll(async ({ workspacePage }) => {
    const db = await createDatabase(
      workspacePage.user,
      'GroupByTest',
      workspacePage.workspace
    )
    table = await createTable(workspacePage.user, 'Tasks', db)
    statusField = await createField(
      workspacePage.user,
      'Status',
      'single_select',
      {
        select_options: [
          { value: 'Todo', color: 'light-blue' },
          { value: 'In progress', color: 'light-yellow' },
          { value: 'Done', color: 'light-green' },
        ],
      },
      table
    )

    // Create rows
    // (Use the batch endpoint to create rows with field values)
    // Note: single_select values need to be set by option id after creation
  })

  test('group headers appear as full-width banners', async ({ page, workspacePage }) => {
    // Navigate to the table
    await page.goto(`/database/${table.database.id}/table/${table.id}`)
    await page.waitForSelector('.grid-view__rows')

    // Enable group-by via the UI or API
    view = await getDefaultGridView(workspacePage.user, table)
    await createViewGroupBy(workspacePage.user, view, statusField)
    await page.reload()
    await page.waitForSelector('.grid-view__group-header')

    const headers = await page.locator('.grid-view__group-header').count()
    expect(headers).toBeGreaterThan(0)
  })

  test('clicking collapse toggle hides group rows', async ({ page }) => {
    await page.goto(`/database/${table.database.id}/table/${table.id}`)
    await page.waitForSelector('.grid-view__group-header')

    // Count rows before collapse
    const rowsBefore = await page.locator('.grid-view__row').count()

    // Click the first collapse toggle
    await page.locator('.grid-view__group-header-toggle').first().click()

    // Wait for rows to update
    await page.waitForTimeout(500)

    // Count rows after collapse — should be fewer
    const rowsAfter = await page.locator('.grid-view__row').count()
    expect(rowsAfter).toBeLessThan(rowsBefore)
  })

  test('clicking expand toggle shows group rows again', async ({ page }) => {
    await page.goto(`/database/${table.database.id}/table/${table.id}`)
    await page.waitForSelector('.grid-view__group-header')

    // Collapse first group
    await page.locator('.grid-view__group-header-toggle').first().click()
    await page.waitForTimeout(500)
    const rowsCollapsed = await page.locator('.grid-view__row').count()

    // Expand first group
    await page.locator('.grid-view__group-header-toggle').first().click()
    await page.waitForTimeout(500)
    const rowsExpanded = await page.locator('.grid-view__row').count()

    expect(rowsExpanded).toBeGreaterThan(rowsCollapsed)
  })

  test('collapse state persists across page refresh', async ({ page }) => {
    await page.goto(`/database/${table.database.id}/table/${table.id}`)
    await page.waitForSelector('.grid-view__group-header')

    // Collapse first group
    await page.locator('.grid-view__group-header-toggle').first().click()
    await page.waitForTimeout(500)
    const rowsBeforeRefresh = await page.locator('.grid-view__row').count()

    // Refresh
    await page.reload()
    await page.waitForSelector('.grid-view__group-header')
    await page.waitForTimeout(500)

    const rowsAfterRefresh = await page.locator('.grid-view__row').count()
    expect(rowsAfterRefresh).toBe(rowsBeforeRefresh)
  })
})
```

- [ ] **Step 3: Run the e2e tests**

Run: `just e2e test e2e-tests/tests/database/grid_view_group_by.spec.ts`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add e2e-tests/fixtures/database/view.ts \
      e2e-tests/tests/database/grid_view_group_by.spec.ts
git commit -m "test(e2e): add grid view group-by collapse e2e tests"
```

---

## Task 11: Final verification and cleanup

- [ ] **Step 1: Run all backend tests**

Run: `just b test backend/tests/baserow/contrib/database/api/views/grid/ -x -v`
Expected: All tests PASS (including existing group-by tests).

- [ ] **Step 2: Run all frontend tests**

Run: `just f test`
Expected: All tests PASS.

- [ ] **Step 3: Run linters**

Run: `just lint`
Expected: No errors.

- [ ] **Step 4: Run full e2e suite**

Run: `just e2e test`
Expected: No regressions.

- [ ] **Step 5: Visual verification**

Open the dev server and test:
1. Grid view without group-bys — identical to before
2. Single group-by — banner headers with collapse toggles
3. Nested group-bys — indented sub-headers
4. Collapse/expand individual groups
5. Collapse parent group — children hidden
6. Expand parent — child collapse state preserved
7. Scroll through a large grouped view
8. Refresh page — collapse state preserved
9. Row creation — appears in correct group
10. Real-time updates — row changes from another tab update correctly

- [ ] **Step 6: Final commit with any cleanup**

```bash
git add -A
git commit -m "chore(database): cleanup and polish collapsible group-by feature"
```

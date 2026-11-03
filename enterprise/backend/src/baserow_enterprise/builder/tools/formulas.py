"""
Formula context of a builder page, used to generate the formulas of its elements,
data sources and workflow actions.
"""

import json
from contextlib import contextmanager
from typing import Any

from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.pages.models import Page
from baserow.core.utils import to_path
from baserow_enterprise.tools.formula_utils import (
    create_example_from_json_schema,
    minimize_json_schema,
)


class BuilderFormulaContext:
    """
    Context for formula generation in builder elements.

    Provides access to data sources, page parameters, current record
    (for repeat/table elements), form data, and user context.
    """

    def __init__(self, page: Page):
        self.page = page
        self.context: dict[str, Any] = {}
        self.context_metadata: dict[str, Any] = {}
        self._current_record_stack: list[int] = []
        self._row_scoped_data_source: int | None = None

    def load_page_context(self) -> None:
        """Load all available data providers into the formula context."""

        self._load_data_sources()
        self._load_data_source_context()
        self._load_page_parameters()
        self._load_user_context()

        elements = ElementHandler().get_elements(self.page, use_cache=False)
        self._load_form_data(elements)

    # -- Private loaders ----------------------------------------------------

    def _load_data_sources(self) -> None:
        """Load data sources with schemas."""

        data_sources = DataSourceHandler().get_data_sources(self.page, with_shared=True)
        for ds in data_sources:
            if not ds.service:
                continue

            service = ds.service.specific
            service_type = service.get_type()

            try:
                schema = service_type.generate_schema(service)
            except Exception:
                continue
            if not schema:
                continue

            key = f"data_source.{ds.id}"
            try:
                example = create_example_from_json_schema(schema)
                fields = minimize_json_schema(schema)
            except (ValueError, KeyError):
                continue

            self.context[key] = example
            self.context_metadata[key] = {
                "name": ds.name,
                "returns_list": service_type.returns_list,
                "fields": fields,
            }

    def _load_page_parameters(self) -> None:
        """Load page path and query parameters."""

        params: dict[str, str] = {}
        params_meta: dict[str, dict] = {}

        for source in (self.page.path_params or [], self.page.query_params or []):
            for p in source:
                name = p.get("name") if isinstance(p, dict) else p
                ptype = p.get("type", "text") if isinstance(p, dict) else "text"
                params[name] = "example_value"
                params_meta[name] = {"type": ptype}

        if params:
            self.context["page_parameter"] = params
            self.context_metadata["page_parameter"] = params_meta

    def _load_data_source_context(self) -> None:
        """Load metadata (total_count) for list data sources."""

        ds_ctx: dict[str, dict] = {}
        ds_ctx_meta: dict[str, dict] = {}

        for key, meta in self.context_metadata.items():
            if not key.startswith("data_source.") or not meta.get("returns_list"):
                continue
            ds_id = key.replace("data_source.", "")
            ds_ctx[ds_id] = {"total_count": 100}
            ds_ctx_meta[ds_id] = {
                "name": meta.get("name", ""),
                "fields": {"total_count": {"type": "number", "desc": "Total records"}},
            }

        if ds_ctx:
            self.context["data_source_context"] = ds_ctx
            self.context_metadata["data_source_context"] = ds_ctx_meta

    def _load_form_data(self, elements: list) -> None:
        """Load form element metadata."""

        from baserow.contrib.builder.elements.mixins import FormElementTypeMixin

        form_data: dict[str, str] = {}
        form_meta: dict[str, dict] = {}

        type_map = {
            "input_text": "string",
            "choice": "string",
            "checkbox": "boolean",
            "datetime_picker": "string",
            "record_selector": "number",
        }

        for element in elements:
            el_type = element.get_type()
            if not isinstance(el_type, FormElementTypeMixin):
                continue

            el = element.specific
            label = getattr(el, "label", None)
            if label and isinstance(label, dict) and "formula" in label:
                label = label["formula"]
            label = str(label) if label else el_type.type

            data_type = type_map.get(el_type.type, "string")
            form_data[str(el.id)] = data_type
            form_meta[str(el.id)] = {
                "type": el_type.type,
                "data_type": data_type,
                "label": label,
            }

        if form_data:
            self.context["form_data"] = form_data
            self.context_metadata["form_data"] = form_meta

    def _load_user_context(self) -> None:
        """Load user data provider context."""

        self.context["user"] = {
            "id": 1,
            "email": "user@example.com",
            "username": "user",
            "role": "member",
            "is_authenticated": True,
        }
        self.context_metadata["user"] = {
            "id": {"type": "number", "desc": "User ID"},
            "email": {"type": "text", "desc": "User email address"},
            "username": {"type": "text", "desc": "Username"},
            "role": {"type": "text", "desc": "User role"},
            "is_authenticated": {
                "type": "boolean",
                "desc": "Whether user is logged in",
            },
        }

    # -- Current record stack -----------------------------------------------

    def push_current_record_context(self, data_source_id: int) -> None:
        """Add current_record context for elements inside collections."""

        self._current_record_stack.append(data_source_id)
        ds_key = f"data_source.{data_source_id}"

        if ds_key in self.context_metadata:
            example = self.context.get(ds_key, {})
            if isinstance(example, list) and example:
                example = example[0]
            self.context["current_record"] = example
            ds_meta = self.context_metadata[ds_key]
            self.context_metadata["current_record"] = {
                "name": ds_meta.get("name", ""),
                "desc": "Current row in the collection element. "
                "Use current_record.field_<id> for row values.",
                **ds_meta.get("fields", {}),
            }

    def pop_current_record_context(self) -> None:
        """Remove current_record context when exiting a collection."""

        if self._current_record_stack:
            self._current_record_stack.pop()

        if not self._current_record_stack:
            self.context.pop("current_record", None)
            self.context_metadata.pop("current_record", None)
        else:
            prev = self._current_record_stack[-1]
            self.push_current_record_context(prev)
            self._current_record_stack.pop()

    # -- FormulaContext interface -------------------------------------------

    def get_formula_context(self) -> dict[str, Any]:
        """Return the context dict for formula generation."""
        return self._scoped_context(self.context)

    def get_context_metadata(self) -> dict[str, Any]:
        """Return metadata about the context."""
        return self._scoped_context(self.context_metadata)

    def _scoped_context(self, values: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in values.items()
            if key != f"data_source.{self._row_scoped_data_source}"
        }

    @contextmanager
    def scope_to_current_record(self):
        """Use the collection row for implicit formulas, keeping other sources."""

        previous = self._row_scoped_data_source
        if self._current_record_stack and "current_record" in self.context:
            self._row_scoped_data_source = self._current_record_stack[-1]
        try:
            yield
        finally:
            self._row_scoped_data_source = previous

    def __getitem__(self, key: str) -> Any:
        """
        Resolve a dotted path through the context.

        Handles compound keys like ``data_source.5.0.field_name`` and
        wildcard ``*`` for array expansion.
        """

        parts = to_path(key)
        if not parts:
            raise KeyError(f"Empty path: {key}")

        value, remaining = self._resolve_root(key, parts)
        value = self._traverse_path(key, value, remaining)
        return self._coerce_leaf(value, key)

    # -- __getitem__ helpers ------------------------------------------------

    def _resolve_root(self, key: str, parts: list[str]) -> tuple[Any, list[str]]:
        """Resolve the root segment, handling ``data_source.{id}`` compound keys."""

        if len(parts) >= 2 and parts[0] == "data_source":
            if parts[1] == str(self._row_scoped_data_source):
                raise KeyError(
                    "This collection's row values are available through "
                    "current_record. Use get('current_record.field_<id>') for "
                    "the row being rendered, not a fixed row of its data source. "
                    "Intentional absolute access requires an explicit formula."
                )
            ds_key = f"data_source.{parts[1]}"
            if ds_key not in self.context:
                raise KeyError(
                    f"Data source '{parts[1]}' not found. "
                    f"Available: {[k for k in self.context if k.startswith('data_source.')]}"
                )
            return self.context[ds_key], parts[2:]
        return self.context, parts

    def _traverse_path(self, key: str, value: Any, parts: list[str]) -> Any:
        """Walk through *parts*, handling dicts, lists, and ``*`` wildcards."""

        for i, part in enumerate(parts):
            if isinstance(value, dict):
                if part not in value:
                    raise KeyError(f"Key '{part}' not found in context at '{key}'")
                value = value[part]
            elif isinstance(value, list):
                if part == "*":
                    return self._expand_wildcard(value, parts[i + 1 :])
                try:
                    idx = int(part)
                except ValueError:
                    raise KeyError(f"Invalid list index '{part}' at '{key}'")
                if idx >= len(value):
                    raise KeyError(
                        f"Index {idx} out of range (len {len(value)}) at '{key}'"
                    )
                value = value[idx]
            else:
                raise KeyError(f"Cannot traverse at '{part}' in '{key}'")
        return value

    @staticmethod
    def _expand_wildcard(items: list, rest: list[str]) -> str:
        """Expand a ``*`` wildcard over *items*, extracting the remaining path."""

        if not rest:
            return json.dumps(items)
        results = []
        for item in items:
            v = item
            for r in rest:
                if isinstance(v, dict) and r in v:
                    v = v[r]
                else:
                    v = None
                    break
            if v is not None:
                results.append(str(v))
        return ",".join(results)

    @staticmethod
    def _coerce_leaf(value: Any, key: str = "") -> Any:
        """Ensure the leaf value is a JSON-serialisable primitive."""

        from datetime import date, datetime

        if isinstance(value, (list, dict)):
            return json.dumps(value)
        if not isinstance(value, (int, float, str, bool, date, datetime, type(None))):
            raise ValueError(
                f"Value for '{key}' is not a primitive. Got {type(value).__name__}."
            )
        return value

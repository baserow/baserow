"""
Formula context of a builder page, used to check and generate the formulas of its
elements, data sources and workflow actions, and the step that stores the formulas a
tool call was given. No model is called here.
"""

import json
from contextlib import contextmanager
from typing import Any, Literal

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.builder.data_sources.actions import UpdateDataSourceActionType
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.elements.actions import UpdateElementActionType
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.mixins import CollectionElementTypeMixin
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.actions import (
    UpdateBuilderWorkflowActionActionType,
)
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.core.exceptions import PermissionException
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import (
    PERMISSION_DENIED_MESSAGE,
    ToolInputError,
    item_error_message,
)
from baserow.core.utils import to_path
from baserow_enterprise.tools.formula_utils import (
    create_example_from_json_schema,
    formula_object,
    is_valid_formula,
    minimize_json_schema,
)

from .types import DataSourceCreate, DataSourceUpdate, ElementUpdate

BuilderFormulaKind = Literal["element", "data_source", "action"]


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


def page_formula_context(page: Page) -> BuilderFormulaContext:
    """The formula context of a page, with its data providers loaded."""

    context = BuilderFormulaContext(page)
    context.load_page_context()
    return context


class BuilderFormulaError(dict):
    """
    A ``formula_errors`` entry. ``source`` and ``item`` stay off the entry the client
    gets, and let a caller that can fill the value write it the way this step would.

    :param kind: The kind of the item.
    :param source: The element, data source or workflow action.
    :param item: The input it was created or updated with.
    """

    def __init__(
        self,
        kind: BuilderFormulaKind,
        source: Any,
        item: Any,
        field: str,
        formula: str,
        error: str,
    ):
        super().__init__(
            {
                f"{kind}_id": source.id,
                "field": field,
                "formula": formula,
                "error": error,
            }
        )
        self.kind = kind
        self.source = source
        self.item = item


def formula_problem(
    field: str, formula: str, context: BuilderFormulaContext
) -> str | None:
    """
    Why a value can't be stored as a formula: it is a description, or it doesn't
    resolve on the page. This is the same check generated formulas pass.

    :return: The problem, or None when the formula is valid.
    """

    if not formula.strip() or not is_valid_formula(formula):
        return (
            f"'{field}' needs a formula, not a description. Write it in Baserow "
            "formula syntax, like get('page_parameter.id')."
        )
    try:
        resolve_formula(
            BaserowFormulaObject.create(formula, mode=BASEROW_FORMULA_MODE_ADVANCED),
            formula_runtime_function_registry,
            context,
        )
    except Exception as exc:
        return f"'{field}' can't be resolved on this page: {exc}"
    return None


def check_required_formulas(
    formulas: dict[str, str], context: BuilderFormulaContext | None
) -> None:
    """
    :param formulas: The values the item can't run without, by field.
    :raises ToolInputError: When one of them can't be stored.
    """

    for field, formula in formulas.items():
        problem = formula_problem(field, formula, context)
        if problem:
            raise ToolInputError(
                f"{problem} It can't run without it, so it wasn't created."
            )


def _formulas_of(kind: BuilderFormulaKind, source: Any, item: Any) -> dict[str, str]:
    if isinstance(item, ElementUpdate):
        return item.get_formulas_to_update(source, None, source.get_type().type)
    if isinstance(item, DataSourceUpdate):
        return item.get_formulas_to_update(source, None)
    return item.get_formulas_to_create(source, None)


@contextmanager
def current_record_of(
    context: BuilderFormulaContext, kind: BuilderFormulaKind, source: Any
):
    """
    Offer the row of the collection around an element or action, or of a collection
    element itself, as current_record.
    """

    data_source_id = None
    if kind != "data_source":
        element = source if kind == "element" else source.element
        try:
            ancestor = ElementHandler().get_first_ancestor_of_type(
                element, CollectionElementTypeMixin
            )
        except KeyError:
            # The parent can be on another page, like a shared page header.
            ancestor = None
        if ancestor:
            data_source_id = ancestor.data_source_id

    if data_source_id:
        context.push_current_record_context(data_source_id)
    try:
        yield
    finally:
        if data_source_id:
            context.pop_current_record_context()


def _write_element_formulas(
    user: AbstractUser, element: Any, item: Any, formulas: dict[str, str]
) -> None:
    fresh = ElementHandler().get_element_for_update(element.id)
    if not isinstance(item, ElementUpdate):
        item.update_with_formulas(user, fresh, formulas)
        return
    values = {
        field: formula_object(formula, mode=BASEROW_FORMULA_MODE_ADVANCED)
        for field, formula in formulas.items()
        if "." not in field and hasattr(element, field)
    }
    dependent = item.get_formula_dependent_fields(element.get_type().type)
    for dependent_field, formula_field in dependent.items():
        if formula_field in values:
            values[dependent_field] = getattr(item, dependent_field)
    if values:
        UpdateElementActionType.do(user, fresh, values)


def _write_data_source_formulas(
    user: AbstractUser, data_source: Any, item: Any, formulas: dict[str, str]
) -> None:
    if isinstance(item, DataSourceCreate):
        # Undoing the create removes these too.
        item.update_with_formulas(user, data_source, formulas)
        return
    fresh = DataSourceHandler().get_data_source_for_update(data_source.id)
    service_type = service_type_registry.get_by_model(fresh.service.specific)
    # An action of its own, so undo restores the previous formula.
    UpdateDataSourceActionType.do(
        user,
        fresh,
        service_type=service_type,
        **{
            field: formula_object(formula, mode=BASEROW_FORMULA_MODE_ADVANCED)
            for field, formula in formulas.items()
        },
    )


def _write_action_formulas(
    user: AbstractUser, action: Any, item: Any, formulas: dict[str, str]
) -> None:
    # A row action's mappings are replaced as a whole list, so a concurrent
    # add_action_field_mapping waits for this.
    service_id = getattr(action, "service_id", None)
    if service_id is not None:
        Service.objects.select_for_update().filter(id=service_id).first()
    fresh = BuilderWorkflowActionHandler().get_workflow_action(action.id)
    values = item.formula_values(fresh, formulas)
    if values:
        UpdateBuilderWorkflowActionActionType.do(user, fresh, **values)


_WRITERS = {
    "element": _write_element_formulas,
    "data_source": _write_data_source_formulas,
    "action": _write_action_formulas,
}


def write_builder_formulas(
    user: AbstractUser,
    kind: BuilderFormulaKind,
    source: Any,
    item: Any,
    formulas: dict[str, str],
) -> None:
    """
    Store formulas on an item, in ADVANCED mode, in a transaction of their own. The
    item is loaded again, locked, so a change made since it was read is kept.
    """

    with transaction.atomic():
        _WRITERS[kind](user, source, item, formulas)


def apply_builder_formulas(
    ctx: ToolContext,
    page: Page,
    items: list[tuple[Any, Any]],
    kind: BuilderFormulaKind,
) -> list[dict]:
    """
    Store the valid formulas of created or updated items and report the others.

    :param items: The elements, data sources or workflow actions, with the input
        they were created or updated with.
    :param kind: What the items are.
    :return: A ``formula_errors`` entry for each value that was not stored: a
        description, a formula that isn't valid on the page, or a write that failed.
    """

    entries: list[dict] = []
    context = None
    for source, item in items:
        formulas = _formulas_of(kind, source, item)
        if not formulas:
            continue
        if context is None:
            context = page_formula_context(page)

        valid: dict[str, str] = {}
        with current_record_of(context, kind, source):
            for field, formula in formulas.items():
                problem = formula_problem(field, formula, context)
                if problem:
                    entries.append(
                        BuilderFormulaError(kind, source, item, field, formula, problem)
                    )
                else:
                    valid[field] = formula
        if not valid:
            continue

        try:
            write_builder_formulas(ctx.user, kind, source, item, valid)
        except Exception as exc:
            error = (
                PERMISSION_DENIED_MESSAGE
                if isinstance(exc, PermissionException)
                else item_error_message(exc)
            )
            entries.extend(
                BuilderFormulaError(kind, source, item, field, formula, error)
                for field, formula in valid.items()
            )
    return entries

"""
Formula context of a builder page, used to generate the formulas of its elements,
data sources and workflow actions, the check of a given formula, and the step that
stores the formulas a tool call was given. No model is called here.
"""

import json
from contextlib import contextmanager
from typing import Any, Literal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from baserow.contrib.automation.tools.formulas import MAX_LISTED_PATHS
from baserow.contrib.builder.data_providers.registries import (
    builder_data_provider_type_registry,
)
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
from baserow.core.exceptions import InstanceTypeDoesNotExist, PermissionException
from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.parser.exceptions import BaserowFormulaException
from baserow.core.formula.parser.formula_validation_visitor import (
    BaserowFormulaValidationVisitor,
)
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
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
        # The page's data sources by ID, with their name and schema if they have one.
        self.data_sources: dict[int, dict[str, Any]] = {}
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
            self.data_sources[ds.id] = {"name": ds.name, "schema": None}
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
            self.data_sources[ds.id]["schema"] = schema

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
    :param can_repair: False when the value is fine and something else failed, so
        asking for another formula wouldn't help.
    :param permission_denied: Whether the user may not write the value.
    """

    def __init__(
        self,
        kind: BuilderFormulaKind,
        source: Any,
        item: Any,
        field: str,
        formula: str,
        error: str,
        can_repair: bool = True,
        permission_denied: bool = False,
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
        self.can_repair = can_repair
        self.permission_denied = permission_denied


class _GetPathsVisitor(BaserowFormulaValidationVisitor):
    """Checks a formula's functions and collects the paths its ``get`` calls read."""

    def __init__(self):
        super().__init__(
            formula_runtime_function_registry,
            data_provider_type_registry=builder_data_provider_type_registry,
        )
        self.paths: list[str] = []

    def _parse_args_for_validation(self, formula_function_type, accepted_args):
        # A path built by another function is only known when the page runs.
        if (
            formula_function_type.type == "get"
            and accepted_args
            and isinstance(accepted_args[0], str)
        ):
            if not to_path(accepted_args[0]):
                raise InvalidRuntimeFormula(
                    f"'{accepted_args[0]}' doesn't name anything to read."
                )
            self.paths.append(accepted_args[0])
        return super()._parse_args_for_validation(formula_function_type, accepted_args)


def _matches_schema(
    segments: list[str], schema: dict[str, Any], by_title: bool = False
) -> bool:
    """
    Whether a path reads something a JSON schema describes.

    :param by_title: Whether a segment may also name a row's field by its name, which
        the row services read too.
    """

    if not segments:
        return True
    if schema.get("type") == "array":
        if not (segments[0].isdigit() or segments[0] == "*"):
            return False
        items = schema.get("items")
        return _matches_schema(segments[1:], items, by_title) if items else True
    properties = schema.get("properties")
    if not properties:
        # An object of unknown shape can hold anything; a plain value holds nothing.
        return schema.get("type") == "object"
    prop = properties.get(segments[0])
    if prop is None and by_title:
        prop = next(
            (p for p in properties.values() if p.get("title") == segments[0]), None
        )
    return prop is not None and _matches_schema(segments[1:], prop)


def _listed(names: list[str]) -> str:
    if len(names) > MAX_LISTED_PATHS:
        names = [*names[:MAX_LISTED_PATHS], "..."]
    return ", ".join(names) or "none"


def _data_source_path_problem(
    path: str,
    rest: list[str],
    context: BuilderFormulaContext,
    check_schema: bool = True,
) -> str | None:
    data_source_id = rest[0] if rest else ""
    data_source = (
        context.data_sources.get(int(data_source_id))
        if data_source_id.isdigit()
        else None
    )
    if data_source is None:
        names = [f"{key} ({ds['name']})" for key, ds in context.data_sources.items()]
        return (
            f"'{path}' reads data source '{data_source_id}', which isn't on this "
            f"page. Its data sources: {_listed(names)}."
        )
    schema = data_source["schema"]
    if (
        not check_schema
        or schema is None
        or _matches_schema(rest[1:], schema, by_title=True)
    ):
        return None
    if schema.get("type") == "array" and not (rest[1].isdigit() or rest[1] == "*"):
        return (
            f"'{path}' needs a row index after the data source, because it returns "
            f"a list, like data_source.{data_source_id}.0.id."
        )
    properties = schema.get("items", schema).get("properties", {})
    names = [f"{key} ({prop.get('title')})" for key, prop in properties.items()]
    return (
        f"'{path}' is not something data source {data_source_id} "
        f"('{data_source['name']}') has. Its fields: {_listed(names)}."
    )


def _get_path_problem(
    path: str, context: BuilderFormulaContext, allow_previous_action: bool
) -> str | None:
    """Why a path of a ``get`` call can't be read in this context, if so."""

    parts = to_path(path)
    if not parts:
        return f"'{path}' doesn't name anything to read."
    root, *rest = parts
    if root == "data_source":
        return _data_source_path_problem(path, rest, context)
    if root == "data_source_context":
        return _data_source_path_problem(path, rest, context, check_schema=False)
    if root in ("page_parameter", "form_data"):
        known = context.context.get(root, {})
        what = "page parameter" if root == "page_parameter" else "form element"
        if not rest or rest[0] not in known:
            return (
                f"'{path}' doesn't name a {what} of this page. "
                f"Its {what}s: {_listed(list(known))}."
            )
    if root == "current_record" and not context._current_record_stack:
        return f"'{path}' can only be read inside a repeat or a table."
    if root == "previous_action" and not allow_previous_action:
        return f"'{path}' can only be read in a workflow action."
    return None


def formula_problem(
    field: str,
    formula: str,
    context: BuilderFormulaContext,
    allow_previous_action: bool = False,
) -> str | None:
    """
    Why a value can't be stored as a formula. The formula isn't evaluated, so the
    type of the values its functions get isn't checked. It must parse, call functions
    that exist and read paths this context has: for ``data_source``, ``page_parameter``
    and ``form_data`` the thing named must exist, and for the other providers the
    provider must be available.

    :param allow_previous_action: Whether the value can read earlier workflow actions.
    :return: The problem, or None when the formula is valid.
    """

    description = (
        f"'{field}' needs a formula, not a description. Write it in Baserow "
        "formula syntax, like get('page_parameter.id')."
    )
    if not formula.strip():
        return description
    try:
        tree = get_parse_tree_for_formula(formula)
    except (BaserowFormulaException, RecursionError):
        return description

    visitor = _GetPathsVisitor()
    try:
        visitor.visit(tree)
    except DjangoValidationError as exc:
        return f"'{field}' is not a valid formula: {' '.join(exc.messages)}"
    except (
        BaserowFormulaException,
        InvalidRuntimeFormula,
        InstanceTypeDoesNotExist,
        RecursionError,
        ValueError,
        OverflowError,
    ) as exc:
        return f"'{field}' is not a valid formula: {exc}"

    for path in visitor.paths:
        problem = _get_path_problem(path, context, allow_previous_action)
        if problem:
            return f"'{field}' can't be read on this page: {problem}"
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


def _formulas_of(source: Any, item: Any) -> dict[str, str]:
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
    item is loaded again inside it, so a change made since it was read is kept. An
    element or data source is locked; for an action, its service is.
    """

    with transaction.atomic():
        _WRITERS[kind](user, source, item, formulas)


def apply_builder_formulas(
    ctx: ToolContext,
    page: Page,
    items: list[tuple[Any, Any]],
    kind: BuilderFormulaKind,
) -> list[BuilderFormulaError]:
    """
    Store the valid formulas of created or updated items and report the others.

    :param items: The elements, data sources or workflow actions, with the input
        they were created or updated with.
    :param kind: What the items are.
    :return: A ``formula_errors`` entry for each value that was not stored: a
        description, a formula that isn't valid on the page, or a failure while
        checking or writing it. The items are already saved, so a failure is reported
        with its item and never stops the others.
    """

    entries: list[BuilderFormulaError] = []
    context = None
    for source, item in items:
        pending: dict[str, str] = {}
        try:
            pending = _formulas_of(source, item)
            if not pending:
                continue
            if context is None:
                context = page_formula_context(page)

            with current_record_of(context, kind, source):
                problems = {
                    field: formula_problem(field, formula, context)
                    for field, formula in pending.items()
                }
            for field, problem in problems.items():
                if problem:
                    entries.append(
                        BuilderFormulaError(
                            kind, source, item, field, pending.pop(field), problem
                        )
                    )
            if pending:
                write_builder_formulas(ctx.user, kind, source, item, pending)
        except Exception as exc:
            denied = isinstance(exc, PermissionException)
            error = PERMISSION_DENIED_MESSAGE if denied else item_error_message(exc)
            entries.extend(
                BuilderFormulaError(
                    kind,
                    source,
                    item,
                    field,
                    formula,
                    error,
                    can_repair=False,
                    permission_denied=denied,
                )
                # No fields means reading them failed, which is still reported.
                for field, formula in (pending or {"": ""}).items()
            )
    return entries

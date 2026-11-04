"""
Application builder data source tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field

from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.pages.models import Page
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import raise_if_permission_denied

from . import BuilderWriteOptions, helpers
from .formulas import (
    apply_builder_formulas,
    check_required_formulas,
    page_formula_context,
)
from .pages import get_page_in_workspace
from .types import (
    DataSourceChanges,
    DataSourceCreate,
    DataSourceItem,
    DataSourceUpdate,
)


def list_data_sources(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
) -> dict[str, Any]:
    """
    List the data sources of a page of an application builder: id, name, type, table
    and page name. Data sources connect the elements of the page to the rows of a
    table. Those with page_name "[shared]" are on the shared page: a page can read them
    too, and they are the only ones a header or footer can read. Create one with
    create_data_sources and the shared_page_id from list_pages.
    """

    page = get_page_in_workspace(ctx, page_id)
    ctx.update_status(_("Listing data sources on %(name)s...") % {"name": page.name})

    data_sources = helpers.list_data_sources_on_page(ctx.user, page)
    return {"data_sources": [ds.model_dump() for ds in data_sources]}


def create_data_sources_with_options(
    ctx: ToolContext,
    page_id: int,
    data_sources: list[DataSourceCreate],
    options: BuilderWriteOptions,
) -> dict[str, Any]:
    """``create_data_sources`` with what a client adds to it."""

    page = get_page_in_workspace(ctx, page_id)
    integration = helpers.get_local_baserow_integration(ctx.user, page.builder)
    context = None
    if not options.defer_required_formulas and any(
        data_source.get_required_formulas() for data_source in data_sources
    ):
        context = page_formula_context(page)

    created: list[dict] = []
    ref_to_id: dict[str, int] = {}
    pairs: list[tuple[DataSource, DataSourceCreate]] = []
    errors: list[str] = []
    with transaction.atomic():
        for ds_create in data_sources:
            ctx.update_status(
                _("Creating data source '%(name)s'...") % {"name": ds_create.name}
            )
            try:
                if not options.defer_required_formulas:
                    check_required_formulas(ds_create.get_required_formulas(), context)
                with transaction.atomic():
                    orm_ds, ds_id = helpers.create_data_source(
                        ctx.user, page, ds_create, integration
                    )
            except Exception as exc:
                raise_if_permission_denied(exc)
                errors.append(f"{ds_create.ref}: {options.item_error(exc)}")
                continue
            ref_to_id[ds_create.ref] = ds_id
            pairs.append((orm_ds, ds_create))
            created.append(
                {
                    "id": ds_id,
                    "ref": ds_create.ref,
                    "name": ds_create.name,
                    "type": ds_create.type,
                }
            )

    formula_errors = apply_builder_formulas(ctx, page, pairs, "data_source")

    result: dict[str, Any] = {
        "created_data_sources": created,
        "ref_to_id_map": ref_to_id,
    }
    if formula_errors:
        result["formula_errors"] = formula_errors
    if errors:
        result["errors"] = errors
    return result


def create_data_sources(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
    data_sources: Annotated[
        list[DataSourceCreate], Field(description="The data sources to create.")
    ],
) -> dict[str, Any]:
    """
    Create data sources on a page, to connect its elements to the rows of a table:
    list_rows for many rows, get_row for one. ref_to_id_map gives the ID of each ref.

    Give dynamic values as formulas in Baserow formula syntax, like
    get('page_parameter.id'). A search_query in plain words is searched for as
    written. Descriptions are not turned into formulas: a search_query that is a
    formula but isn't valid is left empty and listed in formula_errors, so it can be
    set with update_data_source. A get_row can't run without its row_id, so one that
    isn't a number or a valid formula is listed in errors and that data source isn't
    created.
    """

    return create_data_sources_with_options(
        ctx, page_id, data_sources, BuilderWriteOptions()
    )


def update_data_source_on_page(
    ctx: ToolContext, page: Page, data_source: DataSourceUpdate
) -> tuple[DataSource, str, list[dict]]:
    """
    Update a data source of a page or of its builder's shared page.

    :return: The data source, its service type and the ``formula_errors``.
    """

    with transaction.atomic():
        orm_ds, ds_type = helpers.update_data_source(ctx.user, page, data_source)
    formula_errors = apply_builder_formulas(
        ctx, page, [(orm_ds, data_source)], "data_source"
    )
    return orm_ds, ds_type, formula_errors


def update_data_source(
    ctx: ToolContext,
    data_source_id: Annotated[
        int, Field(description="The ID of the data source, from list_data_sources.")
    ],
    data_source: Annotated[
        DataSourceChanges,
        Field(description="The changes. Set only what should change."),
    ],
) -> dict[str, Any]:
    """
    Update a data source: its name, table, view, row_id or search_query. Give dynamic
    values as formulas in Baserow formula syntax, like get('page_parameter.id'). A
    row_id can also be a number, and a search_query in plain words is searched for as
    written. A value that isn't valid keeps its previous value and is listed in
    formula_errors.
    """

    orm_ds = DataSourceHandler().get_data_source(
        data_source_id,
        base_queryset=DataSource.objects.filter(
            page__builder__workspace=ctx.workspace, page__builder__trashed=False
        ),
    )
    page = get_page_in_workspace(ctx, orm_ds.page_id)
    ctx.update_status(_("Updating data source %(id)d...") % {"id": data_source_id})

    _orm_ds, _ds_type, formula_errors = update_data_source_on_page(
        ctx,
        page,
        DataSourceUpdate(
            data_source_id=data_source_id,
            **data_source.model_dump(exclude={"data_source_id"}),
        ),
    )

    updated = DataSourceHandler().get_data_source(data_source_id)
    result: dict[str, Any] = {
        "updated_data_source": DataSourceItem.from_orm(updated).model_dump()
    }
    if formula_errors:
        result["formula_errors"] = formula_errors
    return result

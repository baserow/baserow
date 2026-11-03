"""
Setting up a page, a user source and a theme, without a model. The conftest of this
folder fails any model call.
"""

from django.urls import reverse

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.models import Element, LinkElement
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.exceptions import PageDoesNotExist
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.tools.errors import PERMISSION_DENIED_MESSAGE, ToolInputError
from baserow.core.user_sources.models import UserSource
from baserow_enterprise.builder.elements.element_types import AuthFormElementType
from baserow_enterprise.builder.elements.models import AuthFormElement
from baserow_enterprise.builder.tools import (
    BuilderWriteOptions,
    helpers,
    pages,
    themes,
    user_sources,
)
from baserow_enterprise.builder.tools.types import (
    ActionCreate,
    DataSourceCreate,
    ElementItemCreate,
    TableFieldConfig,
)
from baserow_enterprise.builder.tools.types.user_source import UserSourceSetup


def table_of(builder_ctx):
    return builder_ctx["data_source"].service.specific.table


def setup(builder_ctx, **kwargs):
    kwargs.setdefault("data_sources", None)
    kwargs.setdefault("elements", None)
    kwargs.setdefault("actions", None)
    return pages.setup_page(builder_ctx["ctx"], builder_ctx["page"].id, **kwargs)


@pytest.fixture
def users_table(data_fixture, builder_ctx):
    database = data_fixture.create_database_application(
        workspace=builder_ctx["workspace"]
    )
    table = data_fixture.create_database_table(database=database, name="People")
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_email_field(table=table, name="Email")
    return table


# ---------------------------------------------------------------------------
# setup_page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_setup_page_refs_work_across_its_phases(builder_ctx):
    result = setup(
        builder_ctx,
        data_sources=[
            DataSourceCreate(
                ref="rows",
                name="Rows",
                type="list_rows",
                table_id=table_of(builder_ctx).id,
            )
        ],
        elements=[
            ElementItemCreate(ref="box", type="simple_container"),
            ElementItemCreate(
                ref="btn", type="button", value="Go", parent_element="box"
            ),
            ElementItemCreate(
                ref="list",
                type="table",
                data_source="rows",
                fields=[TableFieldConfig(name="Name")],
            ),
        ],
        actions=[
            ActionCreate(type="notification", element="btn", title="Hi"),
            ActionCreate(type="refresh_data_source", element="btn", data_source="rows"),
        ],
    )

    assert "errors" not in result
    assert "formula_errors" not in result
    data_source = DataSource.objects.get(id=result["created_data_sources"][0]["id"])
    assert data_source.name == "Rows"
    assert [e["ref"] for e in result["created_elements"]] == ["box", "btn", "list"]
    table = Element.objects.get(id=result["created_elements"][2]["id"]).specific
    assert table.data_source_id == data_source.id
    assert [a["type"] for a in result["created_actions"]] == [
        "notification",
        "refresh_data_source",
    ]
    refresh = BuilderWorkflowAction.objects.get(
        id=result["created_actions"][1]["id"]
    ).specific
    assert refresh.data_source_id == data_source.id


@pytest.mark.django_db
def test_setup_page_with_one_bad_element_keeps_the_rest(builder_ctx):
    result = setup(
        builder_ctx,
        data_sources=[
            DataSourceCreate(
                ref="rows",
                name="Rows",
                type="list_rows",
                table_id=table_of(builder_ctx).id,
            )
        ],
        elements=[
            ElementItemCreate(ref="top", type="heading", value="Top"),
            ElementItemCreate(
                ref="bad", type="heading", value="Bad", parent_element="nowhere"
            ),
            ElementItemCreate(ref="btn", type="button", value="Go"),
        ],
        actions=[ActionCreate(type="notification", element="btn", title="Hi")],
    )

    assert [d["ref"] for d in result["created_data_sources"]] == ["rows"]
    assert [e["ref"] for e in result["created_elements"]] == ["top", "btn"]
    assert len(result["created_actions"]) == 1
    assert result["errors"] == [
        "element bad: Unknown ref 'nowhere'. Refs only work inside one call; use the "
        "element ID."
    ]


@pytest.mark.django_db
def test_setup_page_names_the_phase_of_each_error(builder_ctx):
    result = setup(
        builder_ctx,
        data_sources=[
            DataSourceCreate(ref="bad", name="Bad", type="list_rows", table_id=999999)
        ],
        actions=[ActionCreate(type="notification", element="nope", title="Hi")],
    )

    assert result["created_data_sources"] == []
    assert result["created_elements"] == []
    assert result["created_actions"] == []
    assert result["errors"][0].startswith("data_source bad: ")
    assert result["errors"][1].startswith("action notification on nope: ")


@pytest.mark.django_db
def test_setup_page_with_a_get_row_description_fails_that_data_source(builder_ctx):
    result = setup(
        builder_ctx,
        data_sources=[
            DataSourceCreate(
                ref="row",
                name="Row",
                type="get_row",
                table_id=table_of(builder_ctx).id,
                row_id="$formula: the id of the page",
            )
        ],
        elements=[ElementItemCreate(ref="top", type="heading", value="Top")],
    )

    assert result["created_data_sources"] == []
    assert result["errors"][0].startswith("data_source row: ")
    assert [e["ref"] for e in result["created_elements"]] == ["top"]


@pytest.mark.django_db
def test_setup_page_lists_every_formula_it_could_not_store(builder_ctx):
    result = setup(
        builder_ctx,
        data_sources=[
            DataSourceCreate(
                ref="rows",
                name="Rows",
                type="list_rows",
                table_id=table_of(builder_ctx).id,
                search_query="$formula: the search",
            )
        ],
        elements=[
            ElementItemCreate(ref="btn", type="button", value="$formula: the label")
        ],
        actions=[
            ActionCreate(type="notification", element="btn", title="$formula: a title")
        ],
    )

    fields = {
        (key, entry["field"])
        for entry in result["formula_errors"]
        for key in entry
        if key.endswith("_id")
    }
    assert fields == {
        ("data_source_id", "search_query"),
        ("element_id", "value"),
        ("action_id", "title"),
    }


@pytest.mark.django_db
def test_setup_page_with_nothing_to_do_is_refused(builder_ctx):
    with pytest.raises(ToolInputError, match="nothing"):
        setup(builder_ctx)


@pytest.mark.django_db
def test_setup_page_stores_a_column_formula_unless_told_otherwise(builder_ctx):
    def table_element():
        return ElementItemCreate(
            ref="list",
            type="table",
            data_source=builder_ctx["data_source"].id,
            fields=[
                TableFieldConfig(
                    name="Name",
                    type="text",
                    value="get('current_record.id')",
                )
            ],
        )

    shared = pages.setup_page(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        None,
        [table_element()],
        None,
    )
    kuma = pages.setup_page_with_options(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        None,
        [table_element()],
        None,
        BuilderWriteOptions(column_name_beats_formula=True),
    )

    def column_value(result):
        element = Element.objects.get(id=result["created_elements"][0]["id"]).specific
        return element.fields.get().config["value"]["formula"]

    assert column_value(shared) == "get('current_record.id')"
    assert "get('current_record.id')" not in column_value(kuma)


@pytest.mark.django_db
def test_setup_page_runs_the_hook_after_each_phase_it_has(builder_ctx):
    phases = []

    def after_phase(kind, phase):
        # Each phase is saved before the next one starts.
        phases.append(
            (
                kind,
                DataSource.objects.filter(name="Rows").count(),
                Element.objects.filter(page=builder_ctx["page"]).count(),
            )
        )
        return []

    existing = Element.objects.filter(page=builder_ctx["page"]).count()
    pages.setup_page_with_options(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            DataSourceCreate(
                ref="rows",
                name="Rows",
                type="list_rows",
                table_id=table_of(builder_ctx).id,
                search_query="$formula: the search",
            )
        ],
        [ElementItemCreate(ref="h", type="heading", value="Title")],
        None,
        BuilderWriteOptions(after_phase=after_phase),
    )

    assert phases == [
        ("data_source", 1, existing),
        ("element", 1, existing + 1),
    ]


@pytest.mark.django_db
def test_setup_page_what_the_hook_returns_is_what_is_listed(builder_ctx):
    result = pages.setup_page_with_options(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        None,
        [ElementItemCreate(ref="h", type="heading", value="$formula: the title")],
        None,
        BuilderWriteOptions(after_phase=lambda kind, phase: []),
    )

    assert "formula_errors" not in result


@pytest.mark.django_db
def test_setup_page_refused_with_nothing_done_raises(builder_ctx, monkeypatch):
    def deny(*args, **kwargs):
        raise PermissionException()

    monkeypatch.setattr(helpers, "create_element", deny)

    with pytest.raises(PermissionException):
        setup(
            builder_ctx,
            elements=[ElementItemCreate(ref="h", type="heading", value="Title")],
        )


@pytest.mark.django_db
def test_setup_page_refused_part_way_reports_what_was_saved(builder_ctx, monkeypatch):
    def deny(*args, **kwargs):
        raise PermissionException()

    monkeypatch.setattr(helpers, "create_workflow_action", deny)

    result = setup(
        builder_ctx,
        elements=[ElementItemCreate(ref="btn", type="button", value="Go")],
        actions=[ActionCreate(type="notification", element="btn", title="Hi")],
    )

    assert [e["ref"] for e in result["created_elements"]] == ["btn"]
    assert result["created_actions"] == []
    assert result["errors"] == [PERMISSION_DENIED_MESSAGE]
    assert "permission_denied" not in result


@pytest.mark.django_db
def test_setup_page_on_another_workspace_is_refused(data_fixture, builder_ctx):
    other = data_fixture.create_workspace(user=builder_ctx["user"])
    page = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=other)
    )

    with pytest.raises(PageDoesNotExist):
        pages.setup_page(
            builder_ctx["ctx"],
            page.id,
            None,
            [ElementItemCreate(ref="h", type="heading", value="Title")],
            None,
        )


# ---------------------------------------------------------------------------
# Link page parameters
# ---------------------------------------------------------------------------


def link(builder_ctx, value):
    target = Page.objects.create(
        builder=builder_ctx["builder"],
        name=f"Target {Page.objects.count()}",
        order=100,
        path=f"/target-{Page.objects.count()}/:id",
        path_params=[{"name": "id", "type": "text"}],
    )
    return ElementItemCreate(
        ref="go",
        type="link",
        value="Go",
        navigation_type="page",
        navigate_to_page_id=target.id,
        link_page_parameters=[{"name": "id", "value": value}],
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value, error",
    [
        ("$formula: the id", "needs a formula"),
        ("get('page_parameter.nope')", "page parameter"),
        ("no_such_function('x')", "not a valid formula"),
    ],
)
def test_a_link_page_parameter_that_is_not_valid_is_left_empty_and_listed(
    builder_ctx, value, error
):
    result = setup(builder_ctx, elements=[link(builder_ctx, value)])

    element_id = result["created_elements"][0]["id"]
    assert LinkElement.objects.get(id=element_id).page_parameters[0]["value"][
        "formula"
    ] == ("''")
    entry = result["formula_errors"][0]
    assert entry["element_id"] == element_id
    assert entry["field"] == "page_param_0"
    assert error in entry["error"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value, stored",
    [
        (lambda ds: f"get('data_source.{ds}.0.id')", None),
        (lambda ds: "5", "5"),
        (lambda ds: "fixed", "'fixed'"),
    ],
)
def test_a_link_page_parameter_that_is_valid_is_stored(builder_ctx, value, stored):
    formula = value(builder_ctx["data_source"].id)

    result = setup(builder_ctx, elements=[link(builder_ctx, formula)])

    assert "formula_errors" not in result
    element = LinkElement.objects.get(id=result["created_elements"][0]["id"])
    assert element.page_parameters[0]["name"] == "id"
    assert element.page_parameters[0]["value"]["formula"] == (stored or formula)


# ---------------------------------------------------------------------------
# Enterprise-only types and the licence
# ---------------------------------------------------------------------------


def _rest_results(api_client, data_fixture, builder_ctx, users_table):
    """What the REST API answers this user for the two enterprise-only types."""

    token = data_fixture.generate_token(builder_ctx["user"])
    builder = builder_ctx["builder"]
    integration = helpers.get_local_baserow_integration(builder_ctx["user"], builder)
    user_source = api_client.post(
        reverse("api:user_sources:list", kwargs={"application_id": builder.id}),
        {
            "type": "local_baserow",
            "name": "From REST",
            "integration_id": integration.id,
            "table_id": users_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    form = api_client.post(
        reverse("api:builder:element:list", kwargs={"page_id": builder_ctx["page"].id}),
        {"type": "auth_form", "user_source_id": user_source.json().get("id")},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    return user_source, form


@pytest.mark.django_db
@pytest.mark.parametrize("licensed", [False, True])
def test_enterprise_only_types_behave_as_the_rest_api_does(
    request,
    api_client,
    data_fixture,
    enterprise_data_fixture,
    builder_ctx,
    users_table,
    licensed,
):
    if licensed:
        request.getfixturevalue("synced_roles")
        request.getfixturevalue("enable_enterprise")
    else:
        enterprise_data_fixture.delete_all_licenses()

    rest_user_source, rest_form = _rest_results(
        api_client, data_fixture, builder_ctx, users_table
    )
    assert rest_user_source.status_code == 200, rest_user_source.json()
    assert rest_form.status_code == 200, rest_form.json()

    result = user_sources.setup_user_source(
        builder_ctx["ctx"],
        builder_ctx["builder"].id,
        UserSourceSetup(name="Tool", table_id=users_table.id),
    )
    source_id = result["reused_user_source"]["id"]
    created = pages.setup_page(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        None,
        [ElementItemCreate(ref="f", type="auth_form", user_source_id=source_id)],
        None,
    )

    assert "errors" not in created
    form = AuthFormElement.objects.get(id=created["created_elements"][0]["id"])
    assert form.user_source_id == source_id


@pytest.mark.django_db
def test_a_refused_auth_form_gets_the_message_of_the_rest_api(
    api_client, data_fixture, builder_ctx, monkeypatch, users_table
):
    monkeypatch.setattr(AuthFormElementType, "is_deactivated", lambda self, ws: True)

    _user_source, rest_form = _rest_results(
        api_client, data_fixture, builder_ctx, users_table
    )
    assert rest_form.status_code == 400
    assert rest_form.json()["error"] == "ERROR_ELEMENT_TYPE_DEACTIVATED"

    result = setup(builder_ctx, elements=[ElementItemCreate(ref="f", type="auth_form")])

    assert result["created_elements"] == []
    assert result["errors"] == [f"element f: {rest_form.json()['detail']}"]


@pytest.mark.django_db
def test_an_auth_form_with_a_user_source_of_another_builder_is_refused(
    data_fixture, builder_ctx
):
    other = data_fixture.create_builder_application(workspace=builder_ctx["workspace"])
    source = data_fixture.create_user_source_with_first_type(application=other)

    result = setup(
        builder_ctx,
        elements=[
            ElementItemCreate(ref="f", type="auth_form", user_source_id=source.id)
        ],
    )

    assert result["created_elements"] == []
    assert result["errors"]


# ---------------------------------------------------------------------------
# setup_user_source
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_setup_user_source_twice_on_a_table_reuses_the_user_source(
    builder_ctx, users_table
):
    args = (
        builder_ctx["ctx"],
        builder_ctx["builder"].id,
        UserSourceSetup(name="People", table_id=users_table.id),
    )

    first = user_sources.setup_user_source(*args)
    fields = Field.objects.filter(table=users_table).count()
    pages_after_first = Page.objects.count()
    second = user_sources.setup_user_source(*args)

    source = UserSource.objects.get(application=builder_ctx["builder"])
    assert first["created_user_source"]["id"] == source.id
    assert first["created_user_source"]["table_id"] == users_table.id
    assert "reused_user_source" not in first
    assert second["reused_user_source"]["id"] == source.id
    assert "created_user_source" not in second
    assert "created_pages" not in second
    assert second["login_page_id"] == first["login_page_id"]
    assert Field.objects.filter(table=users_table).count() == fields
    assert Page.objects.count() == pages_after_first


@pytest.mark.django_db
def test_setup_user_source_does_not_reuse_a_trashed_or_other_user_source(
    data_fixture, builder_ctx, users_table
):
    other = data_fixture.create_builder_application(workspace=builder_ctx["workspace"])
    args = (
        builder_ctx["ctx"],
        builder_ctx["builder"].id,
        UserSourceSetup(name="People", table_id=users_table.id),
    )
    user_sources.setup_user_source(
        builder_ctx["ctx"],
        other.id,
        UserSourceSetup(name="People", table_id=users_table.id),
    )
    first = user_sources.setup_user_source(*args)
    assert "created_user_source" in first

    UserSource.objects.filter(id=first["created_user_source"]["id"]).update(
        trashed=True
    )

    assert "created_user_source" in user_sources.setup_user_source(*args)


@pytest.mark.django_db
def test_setup_user_source_creates_the_login_page_and_lists_it(
    builder_ctx, users_table
):
    result = user_sources.setup_user_source(
        builder_ctx["ctx"],
        builder_ctx["builder"].id,
        UserSourceSetup(name="People", table_id=users_table.id),
    )

    page = Page.objects.get(id=result["login_page_id"])
    assert page.path == "/login"
    assert [p["id"] for p in result["created_pages"]] == [page.id]
    assert result["created_pages"][0]["path"] == "/login"
    builder_ctx["builder"].refresh_from_db()
    assert builder_ctx["builder"].login_page_id == page.id
    assert AuthFormElement.objects.filter(page=page).count() == 1


@pytest.mark.django_db
def test_setup_user_source_uses_a_public_login_page_without_listing_it(
    data_fixture, builder_ctx, users_table
):
    page = data_fixture.create_builder_page(
        builder=builder_ctx["builder"], name="Sign in", path="/login"
    )

    result = user_sources.setup_user_source(
        builder_ctx["ctx"],
        builder_ctx["builder"].id,
        UserSourceSetup(name="People", table_id=users_table.id),
    )

    assert result["login_page_id"] == page.id
    assert "created_pages" not in result


@pytest.mark.django_db
def test_setup_user_source_does_not_take_a_private_login_path(
    data_fixture, builder_ctx, users_table
):
    private = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Secret",
        path="/login",
        visibility="logged-in",
    )

    result = user_sources.setup_user_source(
        builder_ctx["ctx"],
        builder_ctx["builder"].id,
        UserSourceSetup(name="People", table_id=users_table.id),
    )

    assert result["login_page_id"] != private.id
    assert result["created_pages"][0]["path"] == "/login-1"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("source", ["table_id", "database_id"])
def test_setup_user_source_writes_nothing_when_the_login_page_fails(
    builder_ctx, users_table, monkeypatch, source
):
    def fail(*args, **kwargs):
        raise ToolInputError("No login page.")

    monkeypatch.setattr(helpers, "create_login_page", fail)
    fields = Field.objects.filter(table=users_table).count()
    tables = Table.objects.count()
    setup = (
        UserSourceSetup(name="People", table_id=users_table.id)
        if source == "table_id"
        else UserSourceSetup(name="People", database_id=users_table.database_id)
    )

    with pytest.raises(ToolInputError, match="No login page"):
        user_sources.setup_user_source(
            builder_ctx["ctx"], builder_ctx["builder"].id, setup
        )

    assert not UserSource.objects.filter(application=builder_ctx["builder"]).exists()
    assert Field.objects.filter(table=users_table).count() == fields
    assert Table.objects.count() == tables


@pytest.mark.django_db
def test_setup_user_source_with_a_database_creates_the_table(data_fixture, builder_ctx):
    database = data_fixture.create_database_application(
        workspace=builder_ctx["workspace"]
    )

    result = user_sources.setup_user_source(
        builder_ctx["ctx"],
        builder_ctx["builder"].id,
        UserSourceSetup(name="People", database_id=database.id, roles=["A", "B"]),
    )

    table = Table.objects.get(id=result["table_id"])
    assert table.database_id == database.id
    assert result["created_user_source"]["table_id"] == table.id
    assert set(result["roles"]) >= {"A", "B"}
    assert "password" in result["hint"]


@pytest.mark.django_db
def test_setup_user_source_on_a_table_without_an_email_says_so(
    data_fixture, builder_ctx
):
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=builder_ctx["workspace"]
        )
    )
    data_fixture.create_text_field(table=table, name="Title", primary=True)

    with pytest.raises(ToolInputError, match="missing required fields: email"):
        user_sources.setup_user_source(
            builder_ctx["ctx"],
            builder_ctx["builder"].id,
            UserSourceSetup(name="People", table_id=table.id),
        )


@pytest.mark.django_db
def test_setup_user_source_scopes_table_database_and_builder(data_fixture, builder_ctx):
    other = data_fixture.create_workspace(user=builder_ctx["user"])
    foreign_database = data_fixture.create_database_application(workspace=other)
    foreign_table = data_fixture.create_database_table(database=foreign_database)
    foreign_builder = data_fixture.create_builder_application(workspace=other)
    ctx = builder_ctx["ctx"]
    builder_id = builder_ctx["builder"].id

    with pytest.raises(ToolInputError, match="not found"):
        user_sources.setup_user_source(
            ctx, builder_id, UserSourceSetup(name="P", table_id=foreign_table.id)
        )
    with pytest.raises(ToolInputError, match="not found"):
        user_sources.setup_user_source(
            ctx, builder_id, UserSourceSetup(name="P", database_id=foreign_database.id)
        )
    with pytest.raises(ApplicationDoesNotExist):
        user_sources.setup_user_source(
            ctx,
            foreign_builder.id,
            UserSourceSetup(name="P", database_id=foreign_database.id),
        )
    assert not UserSource.objects.exists()


# ---------------------------------------------------------------------------
# set_theme
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_set_theme_applies_it(builder_ctx):
    result = themes.set_theme(builder_ctx["ctx"], builder_ctx["builder"].id, "eclipse")

    assert result == {"updated_theme": "eclipse"}
    builder = Builder.objects.get(id=builder_ctx["builder"].id)
    assert themes.builder_uses_theme(builder, "eclipse")


@pytest.mark.django_db
def test_set_theme_says_when_the_theme_can_not_be_loaded(builder_ctx, monkeypatch):
    monkeypatch.setattr(themes, "_load_theme_data", lambda name: None)

    with pytest.raises(ToolInputError, match="eclipse"):
        themes.set_theme(builder_ctx["ctx"], builder_ctx["builder"].id, "eclipse")


@pytest.mark.django_db
def test_set_theme_only_works_on_builders_of_the_workspace(data_fixture, builder_ctx):
    database = data_fixture.create_database_application(
        workspace=builder_ctx["workspace"]
    )
    other = data_fixture.create_builder_application(
        workspace=data_fixture.create_workspace(user=builder_ctx["user"])
    )

    for application_id in (database.id, other.id):
        with pytest.raises(ApplicationDoesNotExist):
            themes.set_theme(builder_ctx["ctx"], application_id, "eclipse")

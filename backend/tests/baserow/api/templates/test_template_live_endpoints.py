from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED


def make_template_apps(data_fixture, template_type="official"):
    owner = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    if template_type == "official":
        template = data_fixture.create_template(workspace=workspace)
    else:
        template = data_fixture.create_user_template(user=owner, workspace=workspace)

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        user=owner, application=builder
    )
    page = data_fixture.create_builder_page(builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, integration=integration, table=table
    )
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    widget = data_fixture.create_summary_widget(dashboard=dashboard)

    return {
        "owner": owner,
        "template": template,
        "page": page,
        "data_source": data_source,
        "dashboard": dashboard,
        "widget": widget,
    }


def run(api_client, apps, endpoint, headers):
    requests = {
        "page_dispatch": lambda: api_client.post(
            reverse(
                "api:builder:data_source:dispatch-all",
                kwargs={"page_id": apps["page"].id},
            ),
            {},
            format="json",
            **headers,
        ),
        "single_dispatch": lambda: api_client.post(
            reverse(
                "api:builder:data_source:dispatch",
                kwargs={"data_source_id": apps["data_source"].id},
            ),
            {},
            format="json",
            **headers,
        ),
        "record_names": lambda: api_client.get(
            reverse(
                "api:builder:data_source:record-names",
                kwargs={"data_source_id": apps["data_source"].id},
            ),
            {"record_ids": "1"},
            **headers,
        ),
        "dashboard_dispatch": lambda: api_client.post(
            reverse(
                "api:dashboard:data_sources:dispatch",
                kwargs={"data_source_id": apps["widget"].data_source_id},
            ),
            {},
            format="json",
            **headers,
        ),
    }
    return requests[endpoint]()


RUN_ENDPOINTS = [
    "page_dispatch",
    "single_dispatch",
    "record_names",
    "dashboard_dispatch",
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "template_type,signed_in,endpoint",
    [("user", True, endpoint) for endpoint in RUN_ENDPOINTS]
    + [("official", False, "record_names")],
)
def test_run_endpoints_refused_on_templates(
    api_client, data_fixture, endpoint, template_type, signed_in
):
    apps = make_template_apps(data_fixture, template_type)
    headers = {}
    if signed_in:
        token = data_fixture.generate_token(apps["owner"])
        headers["HTTP_AUTHORIZATION"] = f"JWT {token}"

    response = run(api_client, apps, endpoint, headers)

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_run_endpoints_allowed_signed_in_on_official_template(api_client, data_fixture):
    apps = make_template_apps(data_fixture)
    _, token = data_fixture.create_user_and_token()

    response = run(
        api_client, apps, "page_dispatch", {"HTTP_AUTHORIZATION": f"JWT {token}"}
    )

    assert response.status_code == HTTP_200_OK
    assert list(response.json()) == [str(apps["data_source"].id)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state,with_link,allowed",
    [
        ("official", False, True),
        ("shared", True, True),
        ("shared", False, False),
        ("blocked", False, False),
    ],
    ids=["official", "private_with_link", "private_without_link", "blocked"],
)
def test_dashboard_lists_signed_out(
    api_client, data_fixture, state, with_link, allowed
):
    apps = make_template_apps(
        data_fixture, "official" if state == "official" else "user"
    )
    template = apps["template"]
    if state != "official":
        template = data_fixture.set_user_template_state(template, state)
    headers = {}
    if with_link:
        headers["HTTP_BASEROW_TEMPLATE_AUTHORIZATION"] = template.private_link_token
    dashboard_id = apps["dashboard"].id

    widgets = api_client.get(
        reverse("api:dashboard:widgets:list", kwargs={"dashboard_id": dashboard_id}),
        **headers,
    )
    data_sources = api_client.get(
        reverse(
            "api:dashboard:data_sources:list", kwargs={"dashboard_id": dashboard_id}
        ),
        **headers,
    )

    if allowed:
        assert (widgets.status_code, data_sources.status_code) == (200, 200)
        assert [widget["id"] for widget in widgets.json()] == [apps["widget"].id]
        assert [source["id"] for source in data_sources.json()] == [
            apps["widget"].data_source_id
        ]
    else:
        assert [
            (response.status_code, response.json()["error"])
            for response in [widgets, data_sources]
        ] == [(HTTP_401_UNAUTHORIZED, "PERMISSION_DENIED")] * 2


@pytest.mark.django_db
@pytest.mark.parametrize("exists", [True, False], ids=["regular", "missing"])
def test_dashboard_lists_refused_signed_out_outside_templates(
    api_client, data_fixture, exists
):
    workspace = data_fixture.create_workspace(user=data_fixture.create_user())
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    dashboard_id = dashboard.id if exists else dashboard.id + 1000

    responses = [
        api_client.get(reverse(name, kwargs={"dashboard_id": dashboard_id}))
        for name in ["api:dashboard:widgets:list", "api:dashboard:data_sources:list"]
    ]

    assert [response.status_code for response in responses] == [
        HTTP_401_UNAUTHORIZED
    ] * 2

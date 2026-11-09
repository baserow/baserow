from django.urls import reverse

import pytest

from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.core.import_export.exceptions import ImportExportResourceInvalidFile
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow_enterprise.builder.elements.element_types import HTMLElementType


@pytest.mark.django_db
def test_html_element_round_trip(
    api_client, enterprise_data_fixture, enable_enterprise
):
    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    url = reverse("api:builder:element:list", args=[page.id])
    html = (
        '  <section id="anchor" class="widget" data-lang="en" aria-label="Demo">'
        '<a href="java script:docs">Docs</a><form><input name="attributes"></form>'
        '<div srcdoc="metadata"></div><iframe srcdoc="&lt;p&gt;Static&lt;/p&gt;"></iframe>'
        '<svg><set attributeName="href" to="#target"/></svg>'
        "{{ widget }}<textarea><script>literal text</script></textarea></section>  "
    )
    response = api_client.post(
        url, {"type": "html", "html": html}, format="json", **auth
    )
    assert response.status_code == 200, response.json()
    assert response.json()["html"] == html
    element_id = response.json()["id"]
    item = reverse("api:builder:element:item", args=[element_id])
    html += "<p>Updated</p>"
    assert (
        api_client.patch(item, {"html": html}, format="json", **auth).json()["html"]
        == html
    )
    assert api_client.get(url, **auth).json()[0]["html"] == html
    duplicate = reverse("api:builder:element:duplicate", args=[element_id])
    assert api_client.post(duplicate, **auth).json()["elements"][0]["html"] == html


INVALID_HTML = [
    "<ScRiPt src='/loader.js'></sCrIpT>",
    "<img src=x oNeRrOr=alert(1)>",
    '<a href=" &#x0A;jAvA&#x09;ScRiPt&colon;alert(1)">click</a>',
    '<svg><a xlink:href="javascript:alert(1)">open</a></svg>',
    '<select><option><img src=x onerror="alert(1)"></select>',
    '<template><tr><td onclick="alert(1)">Click</td></tr></template>',
    '<meta http-equiv="refresh" content="0; URL=java&#9;script:alert(1)">',
    '<img srcset="photo.jpg 1x, javascript:alert(1) 2x">',
    '<a ping="/log javascript:alert(1)">Open</a>',
    '<svg><set attributeName="href" to="javascript:alert(1)"/></svg>',
    '<iframe srcdoc="&lt;body onload=alert(1)>"></iframe>',
    '<iframe srcdoc="&lt;script>alert(1)&lt;/script>"></iframe>',
]


@pytest.mark.django_db
@pytest.mark.parametrize("html", INVALID_HTML)
def test_html_rejects_javascript(
    api_client, enterprise_data_fixture, enable_enterprise, html
):
    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    url = reverse("api:builder:element:list", args=[page.id])
    response = api_client.post(
        url, {"type": "html", "html": html}, format="json", **auth
    )
    assert response.status_code == 400
    assert "Custom code" in response.json()["detail"]["html"][0]["error"]
    original = "<p>Original</p>"
    created = api_client.post(
        url, {"type": "html", "html": original}, format="json", **auth
    )
    item = reverse("api:builder:element:item", args=[created.json()["id"]])
    assert (
        api_client.patch(item, {"html": html}, format="json", **auth).status_code == 400
    )
    assert api_client.get(url, **auth).json()[0]["html"] == original


@pytest.mark.django_db
def test_html_element_requires_permission_and_license(
    api_client, enterprise_data_fixture, enable_enterprise
):
    user, token = enterprise_data_fixture.create_user_and_token()
    _, outsider = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    url = reverse("api:builder:element:list", args=[page.id])
    data = {"type": "html", "html": "<p>Only editors</p>"}
    denied = api_client.post(
        url, data, format="json", HTTP_AUTHORIZATION=f"JWT {outsider}"
    )
    assert denied.status_code in (401, 403)
    enterprise_data_fixture.delete_all_licenses()
    denied = api_client.post(
        url, data, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert denied.json()["error"] == "ERROR_ELEMENT_TYPE_DEACTIVATED"


@pytest.mark.django_db
def test_html_import_requires_trust_before_publication(
    api_client, enterprise_data_fixture, enable_enterprise
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_builder_application(user=user)
    page = enterprise_data_fixture.create_builder_page(builder=builder)
    html = '<div id="map" data-lat="48.8"></div>'
    enterprise_data_fixture.create_builder_element(
        HTMLElementType, page=page, html=html
    )
    app_type = application_type_registry.get("builder")
    config = ImportExportConfig(include_permission_data=False)
    exported = app_type.export_serialized(builder, config)
    imported = app_type.import_serialized(builder.workspace, exported, config, {})
    imported.refresh_from_db()
    assert imported.untrusted_content
    imported_page = imported.visible_pages.get()
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    elements = reverse("api:builder:element:list", args=[imported_page.id])
    (element,) = api_client.get(elements, **auth).json()
    assert element["html"] == html
    assert imported.import_report == [
        {
            "type": "html",
            "id": element["id"],
            "page_name": page.name,
            "page_id": imported_page.id,
        }
    ]
    domain = enterprise_data_fixture.create_builder_custom_domain(builder=imported)
    publish = reverse("api:builder:domains:publish", args=[domain.id])
    assert (
        api_client.post(publish, **auth).json()["error"]
        == "ERROR_UNTRUSTED_CONTENT_CANNOT_BE_PUBLISHED"
    )
    trust = reverse("api:applications:item", args=[imported.id])
    assert (
        api_client.patch(
            trust, {"untrusted_content": False}, format="json", **auth
        ).json()["untrusted_content"]
        is False
    )
    published = DomainHandler().publish(domain).published_to
    assert not published.untrusted_content
    public_elements = reverse(
        "api:builder:domains:list_elements", args=[published.visible_pages.get().id]
    )
    assert api_client.get(public_elements).json()[0]["html"] == html


@pytest.mark.django_db
@pytest.mark.parametrize("html", INVALID_HTML[:3])
def test_html_import_cannot_bypass_validation(
    enterprise_data_fixture, enable_enterprise, html
):
    builder = enterprise_data_fixture.create_builder_application()
    page = enterprise_data_fixture.create_builder_page(builder=builder)
    enterprise_data_fixture.create_builder_element(
        HTMLElementType, page=page, html="<p>Safe</p>"
    )
    app_type = application_type_registry.get("builder")
    config = ImportExportConfig(include_permission_data=False)
    serialized = app_type.export_serialized(builder, config)
    exported_page = next(p for p in serialized["pages"] if p["id"] == page.id)
    exported_page["elements"][0]["html"] = html
    serialized["untrusted_content"] = False
    with pytest.raises(ImportExportResourceInvalidFile, match="Custom code"):
        app_type.import_serialized(builder.workspace, serialized, config, {})


@pytest.mark.django_db
@pytest.mark.parametrize("flag", ["is_duplicate", "is_publishing", "is_template"])
def test_internal_html_copies_preserve_trust(
    enterprise_data_fixture, enable_enterprise, flag
):
    builder = enterprise_data_fixture.create_builder_application()
    page = enterprise_data_fixture.create_builder_page(builder=builder)
    enterprise_data_fixture.create_builder_element(
        HTMLElementType, page=page, html="<p>Widget</p>"
    )
    config = ImportExportConfig(include_permission_data=False, **{flag: True})
    app_type = application_type_registry.get("builder")
    copy = app_type.import_serialized(
        builder.workspace, app_type.export_serialized(builder, config), config, {}
    )
    copy.refresh_from_db()
    assert not copy.untrusted_content
    assert copy.import_report[0]["type"] == "html"


@pytest.mark.django_db
def test_empty_html_import_does_not_require_trust(
    enterprise_data_fixture, enable_enterprise
):
    builder = enterprise_data_fixture.create_builder_application()
    page = enterprise_data_fixture.create_builder_page(builder=builder)
    enterprise_data_fixture.create_builder_element(
        HTMLElementType, page=page, html="  "
    )
    config = ImportExportConfig(include_permission_data=False)
    app_type = application_type_registry.get("builder")
    imported = app_type.import_serialized(
        builder.workspace, app_type.export_serialized(builder, config), config, {}
    )
    assert not imported.untrusted_content
    assert imported.import_report == []

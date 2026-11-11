from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK


def test_redoc_uses_pinned_compatible_bundle(api_client):
    response = api_client.get(reverse("api:redoc"))

    assert response.status_code == HTTP_200_OK
    html = response.content.decode()
    assert f'<redoc spec-url="{reverse("api:json_schema")}"></redoc>' in html
    assert (
        'src="https://cdn.jsdelivr.net/npm/redoc@2.5.4/bundles/redoc.standalone.js"'
        in html
    )


def test_can_generate_open_api_schema(api_client):
    response = api_client.get(reverse("api:json_schema"))
    assert response.status_code == HTTP_200_OK

    # The second request is going to be cached. This is to make sure that's working.
    response = api_client.get(reverse("api:json_schema"))
    assert response.status_code == HTTP_200_OK

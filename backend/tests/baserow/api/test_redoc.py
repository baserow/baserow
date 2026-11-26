from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND


def test_redoc_loads_its_assets_from_the_backend(api_client):
    url = reverse("api:redoc")
    response = api_client.get(url)

    assert response.status_code == HTTP_200_OK
    page = BeautifulSoup(response.content, "html.parser")
    assert page.redoc["spec-url"] == reverse("api:json_schema")
    policy = page.find("meta", attrs={"http-equiv": "Content-Security-Policy"})
    assert policy["content"] == "img-src 'self' data:"
    for tag in page.select("[src], link[href]"):
        asset = urlsplit(urljoin(url, tag.get("src") or tag["href"]))
        assert not asset.netloc

    bundle_url = urljoin(url, page.script["src"])
    bundle = api_client.get(bundle_url)
    assert bundle.status_code == HTTP_200_OK
    assert "javascript" in bundle["Content-Type"]
    assert b"Redoc" in b"".join(bundle.streaming_content)
    assert api_client.head(f"{bundle_url}.LICENSE.txt").status_code == HTTP_200_OK
    assert api_client.head(f"{bundle_url}.map").status_code == HTTP_200_OK
    assert api_client.get(f"{bundle_url}.unknown").status_code == HTTP_404_NOT_FOUND


def test_can_generate_open_api_schema(api_client):
    response = api_client.get(reverse("api:json_schema"))
    assert response.status_code == HTTP_200_OK

    # The second request is going to be cached. This is to make sure that's working.
    response = api_client.get(reverse("api:json_schema"))
    assert response.status_code == HTTP_200_OK

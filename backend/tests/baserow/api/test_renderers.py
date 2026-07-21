import gc
import weakref

from django.shortcuts import reverse

import pytest
from rest_framework import serializers
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.status import HTTP_200_OK

from baserow.api.renderers import BaserowJSONRenderer


@pytest.mark.django_db
def test_rendered_response_graph_is_reference_count_collectable(
    api_client, data_fixture
):
    """
    The BaserowJSONRenderer must sever the DRF reference cycles after rendering,
    so that the whole per-request payload (fetched rows, serialized data, rendered
    content) is freed by reference counting alone, without depending on a cyclic
    garbage collection pass. This is what keeps the worker memory flat when large
    values are listed.
    """

    user, jwt_token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Notes")
    table.get_model().objects.create(**{field.db_column: "value"})

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})

    gc.collect()
    gc.disable()
    try:
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {jwt_token}")
        assert response.status_code == HTTP_200_OK

        # The renderer must have cleared the cyclic renderer context, while the
        # public response API stays usable.
        assert response.renderer_context is None
        results = response.data["results"]
        assert results[0][f"field_{field.id}"] == "value"

        # The serializer graph must no longer pin the fetched rows or the
        # serialized output.
        serializer = results.serializer
        assert serializer.instance is None
        assert serializer._data is None
        assert serializer.child._args == ()

        # The Django test client attaches `response.json = partial(...,
        # response)`, a self-cycle that only exists in tests, not in the real
        # request path, and would mask the behavior being verified here.
        response.__dict__.pop("json", None)

        response_ref = weakref.ref(response)
        results_ref = weakref.ref(results)
        del response, results, serializer

        # The garbage collector is disabled, so these can only be dead if the
        # object graph was freed by pure reference counting.
        assert response_ref() is None
        assert results_ref() is None
    finally:
        gc.enable()


def test_renderer_skips_cleanup_when_another_renderer_delegates_to_it():
    class FakeView:
        response = "sentinel-response"
        request = "sentinel-request"

    class FakeResponse:
        accepted_renderer = BrowsableAPIRenderer()

    view = FakeView()
    response = FakeResponse()
    renderer_context = {"view": view, "request": "request", "response": response}

    BaserowJSONRenderer().render({"a": 1}, "application/json", renderer_context)

    assert renderer_context["request"] == "request"
    assert view.response == "sentinel-response"
    assert view.request == "sentinel-request"


class _NameSerializer(serializers.Serializer):
    name = serializers.CharField()


@pytest.mark.parametrize(
    "wrap_data",
    [
        # Serializer output inside an ordinary list, e.g. the job and
        # application APIs.
        lambda data: [data],
        # The kanban/calendar grouped-row shape.
        lambda data: {"rows": {"1": {"count": 1, "results": data}}},
    ],
)
def test_renderer_releases_nested_serializer_outputs(wrap_data):
    serializer = _NameSerializer(instance=[{"name": "a"}], many=True)
    data = serializer.data

    renderer = BaserowJSONRenderer()

    class FakeResponse:
        accepted_renderer = renderer

    renderer.render(
        wrap_data(data),
        "application/json",
        {"response": FakeResponse()},
    )

    assert serializer.instance is None
    assert serializer._data is None
    assert serializer.child._args == ()


def test_renderer_releases_serializer_context():
    class Marker:
        pass

    marker = Marker()
    serializer = _NameSerializer(
        instance=[{"name": "a"}], many=True, context={"marker": marker}
    )
    data = serializer.data

    renderer = BaserowJSONRenderer()

    class FakeResponse:
        accepted_renderer = renderer

    renderer.render(data, "application/json", {"response": FakeResponse()})

    marker_ref = weakref.ref(marker)
    gc.disable()
    try:
        del marker
        # Only dead without gc if the serializer no longer holds the context.
        assert marker_ref() is None
    finally:
        gc.enable()

import gc
import weakref

from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.fields.handler import FieldHandler


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
    field = FieldHandler().create_field(
        user=user, table=table, type_name="text", name="Notes"
    )
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

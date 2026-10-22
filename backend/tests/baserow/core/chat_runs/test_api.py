import json
from collections.abc import Callable
from uuid import uuid4

from django.http import HttpResponseBase, StreamingHttpResponse
from django.urls import reverse

import pytest
from asgiref.sync import async_to_sync

from baserow.api.chat_runs.views import encode_records
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.service import ChatRunService

pytestmark = pytest.mark.django_db


def url(name, run_id):
    return reverse(f"api:chat_runs:{name}", kwargs={"run_id": run_id})


def test_durable_result_is_available_without_redis(
    api_client, data_fixture, create_run, mocker
):
    user, token = data_fixture.create_user_and_token()
    run = create_run(user=user, claim=True)
    ChatRunHandler().finish_run(
        run.id, "completed", message={"id": 15, "content": "saved"}
    )
    mocker.patch(
        "baserow.core.chat_runs.buffer.ChatRunBuffer",
        side_effect=AssertionError("Redis must not be read"),
    )
    response = api_client.get(url("detail", run.id), HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 200
    assert response.json()["message"] == {"id": 15, "content": "saved"}
    assert response.json()["status"] == "completed"


@pytest.mark.parametrize(
    "method,name", [("get", "detail"), ("post", "cancel"), ("get", "stream")]
)
@pytest.mark.parametrize("unknown", [False, True])
def test_run_identity_grants_no_access(
    api_client, data_fixture, create_run, method, name, unknown
):
    _, token = data_fixture.create_user_and_token()
    run = create_run()
    response = getattr(api_client, method)(
        url(name, uuid4() if unknown else run.id), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == 404
    run.refresh_from_db()
    assert run.status == "queued"


def test_read_does_not_grant_cancel(
    api_client, data_fixture, create_run, fake_run_type
):
    user, token = data_fixture.create_user_and_token()
    run = create_run(user=user)
    fake_run_type.allow_cancel = False
    assert (
        api_client.get(
            url("detail", run.id), HTTP_AUTHORIZATION=f"JWT {token}"
        ).status_code
        == 200
    )
    response = api_client.post(url("cancel", run.id), HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 404
    run.refresh_from_db()
    assert run.status == "queued"


def test_cancel_does_not_require_read_permission(
    api_client, data_fixture, create_run, fake_run_type
):
    user, token = data_fixture.create_user_and_token()
    run = create_run(user=user)
    fake_run_type.allow_read = False
    response = api_client.post(url("cancel", run.id), HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == 200
    assert response.json() == {"status": "cancelled"}


def test_read_permission_is_rechecked_after_revocation(create_run, fake_run_type):
    run = create_run()
    assert ChatRunService().snapshot(run.created_by, run.id)["status"] == "queued"
    fake_run_type.allow_read = False
    from baserow.core.chat_runs.exceptions import ChatRunDoesNotExist

    with pytest.raises(ChatRunDoesNotExist):
        ChatRunService().snapshot(run.created_by, run.id)


@pytest.mark.django_db(transaction=True)
def test_snapshot_and_cancel_pin_adapter_permission_queries_to_primary(
    create_run, fake_run_type
):
    from baserow.config.db_routers import clear_db_state, set_db_alias
    from baserow.core.models import Workspace

    run = create_run()

    def allowed(user, run):
        return Workspace.objects.filter(id=run.workspace_id).exists()

    fake_run_type.can_read = allowed
    fake_run_type.can_cancel = allowed
    try:
        set_db_alias("unavailable_replica")
        assert ChatRunService().snapshot(run.created_by, run.id)["status"] == "queued"
        set_db_alias("unavailable_replica")
        assert ChatRunService().request_cancel(run.created_by, run.id) == "cancelled"
    finally:
        clear_db_state()


CURSOR = f"{'a' * 32}:1-0"


async def read_body(response: StreamingHttpResponse) -> str:
    return "".join([part.decode() async for part in response.streaming_content])


@pytest.fixture
def request_stream(
    api_client, data_fixture, create_run
) -> Callable[..., HttpResponseBase]:
    user, token = data_fixture.create_user_and_token()
    run = create_run(user=user)

    def request(query: str = "", method: str = "get") -> HttpResponseBase:
        return getattr(api_client, method)(
            url("stream", run.id) + query, HTTP_AUTHORIZATION=f"JWT {token}"
        )

    return request


def test_stream_encodes_records_from_the_given_cursor(request_stream, mocker):
    delta = {
        "kind": "text.delta",
        "data": {"segment": 0, "text": "Hi"},
        "cursor": f"{'a' * 32}:2-0",
        "replayed": False,
    }
    cursors = []

    async def follow_run(run, user, cursor=None):
        cursors.append(cursor)
        yield {"kind": "run.heartbeat", "data": {}, "cursor": cursor, "replayed": False}
        yield delta

    mocker.patch("baserow.api.chat_runs.views.follow_run", follow_run)
    response = request_stream(f"?cursor={CURSOR}")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"
    assert async_to_sync(read_body)(response) == "\n\n" + json.dumps(delta) + "\n\n"
    assert cursors == [CURSOR]


def test_closing_the_stream_closes_the_follower(mocker):
    closed = []

    async def follow_run(run, user, cursor=None):
        try:
            yield {"kind": "text.delta"}
        finally:
            closed.append(True)

    mocker.patch("baserow.api.chat_runs.views.follow_run", follow_run)

    async def close_after_first_record() -> list[bool]:
        records = encode_records(None, None, None)
        await anext(records)
        await records.aclose()
        return list(closed)

    assert async_to_sync(close_after_first_record)() == [True]


def test_stream_rejects_an_invalid_cursor(request_stream):
    response = request_stream("?cursor=nope")
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"


def test_stream_rejects_head_requests(request_stream):
    assert request_stream(method="head").status_code == 405

"""
The Wait service. It never sleeps: a wait is a `PendingDispatch` that asks the
consumer owning the run to resume the service once the time has passed. The
runner side is covered in `contrib/automation/nodes/test_wait_node.py`.
"""

from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

import pytest
from freezegun import freeze_time

from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.core.services.types import PendingDispatch
from baserow.test_utils.pytest_conftest import FakeDispatchContext

NOW = "2026-10-30 12:00:00"
NOW_ISO = "2026-10-30T12:00:00+00:00"


def dispatch(service, **context):
    return service.get_type().dispatch(service, FakeDispatchContext(**context))


@pytest.mark.django_db
def test_create_core_wait_service(data_fixture):
    user = data_fixture.create_user()
    service_type = service_type_registry.get("wait")
    values = service_type.prepare_values({"seconds": "5"}, user)
    service = ServiceHandler().create_service(service_type, **values)
    assert service.seconds["formula"] == "5"


@pytest.mark.django_db
def test_update_core_wait_service(data_fixture):
    user = data_fixture.create_user()
    service = data_fixture.create_core_wait_service(seconds="5")
    service_type = service.get_type()
    values = service_type.prepare_values({"seconds": "10"}, user)
    result = ServiceHandler().update_service(service_type, service, **values)
    assert result.service.seconds["formula"] == "10"


@pytest.mark.django_db
def test_core_wait_service_generate_schema(data_fixture):
    service = data_fixture.create_core_wait_service()
    assert service.get_type().generate_schema(service) == {
        "title": f"Wait{service.id}Schema",
        "type": "object",
        "properties": {
            "seconds": {
                "type": "integer",
                "title": "Seconds",
                "description": "The number of seconds waited.",
            },
            "resumed_at": {
                "type": "string",
                "format": "date-time",
                "title": "Resumed at",
                "description": "When the wait ended.",
            },
        },
    }


@pytest.mark.django_db
def test_core_wait_service_export_serialized_keeps_the_formula(data_fixture):
    service = data_fixture.create_core_wait_service(seconds="5")
    serialized = service.get_type().export_serialized(service)
    assert serialized["type"] == "wait"
    assert serialized["seconds"]["formula"] == "5"


# Dispatching -----------------------------------------------------------------


@pytest.mark.django_db
def test_core_wait_service_dispatch_asks_to_be_resumed_after_the_seconds(
    data_fixture,
):
    service = data_fixture.create_core_wait_service(seconds="5")

    with freeze_time(NOW):
        result = dispatch(service)
        resume_at = timezone.now() + timedelta(seconds=5)

    # Nothing is produced yet: the result comes from resume_dispatch().
    assert result.data == {}
    assert result.pending == PendingDispatch(resume_at=resume_at, state={"seconds": 5})


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula,seconds",
    [
        pytest.param("2.0", 2, id="whole float"),
        pytest.param("'7'", 7, id="numeric text"),
    ],
)
def test_core_wait_service_dispatch_accepts_whole_numbers(
    data_fixture, formula, seconds
):
    service = data_fixture.create_core_wait_service(seconds=formula)

    with freeze_time(NOW):
        result = dispatch(service)
        resume_at = timezone.now() + timedelta(seconds=seconds)

    assert result.pending == PendingDispatch(
        resume_at=resume_at, state={"seconds": seconds}
    )


@pytest.mark.django_db
def test_core_wait_service_dispatch_with_zero_seconds_completes_at_once(
    data_fixture,
):
    service = data_fixture.create_core_wait_service(seconds="0")

    with freeze_time(NOW):
        result = dispatch(service)

    assert result.pending is None
    assert result.data == {"seconds": 0, "resumed_at": NOW_ISO}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula",
    [
        pytest.param("", id="empty"),
        pytest.param("'abc'", id="text"),
        pytest.param("1.5", id="fractional"),
        pytest.param("'1.5'", id="fractional text"),
        pytest.param("minus(0, 3)", id="negative"),
        pytest.param("true", id="boolean"),
    ],
)
def test_core_wait_service_dispatch_rejects_an_invalid_number_of_seconds(
    data_fixture, formula
):
    """
    Only a whole, non-negative number of seconds is a wait. Anything else is a
    value error, so the node's error policy applies: nothing is rounded or
    clamped on the user's behalf.
    """

    service = data_fixture.create_core_wait_service(seconds=formula)

    with pytest.raises(InvalidContextContentDispatchException) as exc_info:
        dispatch(service)

    assert str(exc_info.value).startswith('Value error for property "seconds"')


@pytest.mark.django_db
@override_settings(AUTOMATION_WAIT_MAX_SECONDS=10)
def test_core_wait_service_dispatch_refuses_a_wait_over_the_maximum(data_fixture):
    service = data_fixture.create_core_wait_service(seconds="11")

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        dispatch(service)

    assert (
        str(exc_info.value)
        == "The wait of 11 seconds exceeds the maximum of 10 seconds."
    )


@pytest.mark.django_db
@override_settings(AUTOMATION_WAIT_MAX_SECONDS=10)
def test_core_wait_service_dispatch_accepts_a_wait_at_the_maximum(data_fixture):
    service = data_fixture.create_core_wait_service(seconds="10")

    with freeze_time(NOW):
        result = dispatch(service)

    assert result.pending.state == {"seconds": 10}


@pytest.mark.django_db
def test_core_wait_service_dispatch_never_waits_with_sample_data(data_fixture):
    """
    A simulation completes at once, and what it stores as sample data is the
    result a real wait would have produced, with nothing pending in it.
    """

    service = data_fixture.create_core_wait_service(seconds="3600")

    with freeze_time(NOW):
        result = dispatch(service, use_sample_data=True)

    assert result.pending is None
    assert result.data == {"seconds": 3600, "resumed_at": NOW_ISO}

    service.refresh_from_db()
    assert service.sample_data["data"] == {"seconds": 3600, "resumed_at": NOW_ISO}
    assert "pending" not in service.sample_data


@pytest.mark.django_db
@override_settings(AUTOMATION_WAIT_MAX_SECONDS=10)
def test_core_wait_service_dispatch_with_sample_data_still_applies_the_maximum(
    data_fixture,
):
    """A simulation shows the error a real run would hit, instead of hiding it."""

    service = data_fixture.create_core_wait_service(seconds="11")

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        dispatch(service, use_sample_data=True)


@pytest.mark.django_db
def test_core_wait_service_resume_dispatch_returns_the_final_result(data_fixture):
    service = data_fixture.create_core_wait_service(seconds="5")

    with freeze_time("2026-10-30 12:00:05"):
        result = service.get_type().resume_dispatch(
            service, {"seconds": 5}, FakeDispatchContext()
        )

    assert result.pending is None
    assert result.data == {"seconds": 5, "resumed_at": "2026-10-30T12:00:05+00:00"}

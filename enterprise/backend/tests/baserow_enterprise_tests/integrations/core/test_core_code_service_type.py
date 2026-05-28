import pytest

from baserow.core.code_runner.registries import (
    CodeRunnerExecutionError,
    CodeRunnerResultError,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.test_utils.pytest_conftest import FakeDispatchContext


class FakeCodeRunner:
    def __init__(self, result=None, exception=None):
        self.result = result or {"newValue": 4}
        self.exception = exception
        self.calls = []

    def run(self, context_data, code):
        self.calls.append((context_data, code))
        if self.exception:
            raise self.exception
        return self.result


@pytest.mark.django_db
def test_core_code_service_type_dispatch_resolves_injections(
    enterprise_data_fixture, monkeypatch
):
    service = enterprise_data_fixture.create_enterprise_core_code_service(
        code="function main(context) { return { newValue: 4 } }"
    )
    service.injections.create(name="value", formula="get('value')")

    code_runner = FakeCodeRunner()
    monkeypatch.setattr(
        "baserow_enterprise.integrations.core.service_types.get_code_runner",
        lambda: code_runner,
    )

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(context={"value": 2}),
    )

    assert dispatch_result.data == {"newValue": 4}
    assert code_runner.calls == [
        (
            {"value": 2},
            "function main(context) { return { newValue: 4 } }",
        )
    ]


@pytest.mark.django_db
def test_core_code_service_type_dispatch_maps_execution_errors(
    enterprise_data_fixture, monkeypatch
):
    service = enterprise_data_fixture.create_enterprise_core_code_service(code="")
    code_runner = FakeCodeRunner(exception=CodeRunnerExecutionError("boom"))
    monkeypatch.setattr(
        "baserow_enterprise.integrations.core.service_types.get_code_runner",
        lambda: code_runner,
    )

    with pytest.raises(UnexpectedDispatchException, match="boom"):
        service.get_type().dispatch(service, FakeDispatchContext())


@pytest.mark.django_db
def test_core_code_service_type_dispatch_maps_result_errors(
    enterprise_data_fixture, monkeypatch
):
    service = enterprise_data_fixture.create_enterprise_core_code_service(code="")
    code_runner = FakeCodeRunner(exception=CodeRunnerResultError("object required"))
    monkeypatch.setattr(
        "baserow_enterprise.integrations.core.service_types.get_code_runner",
        lambda: code_runner,
    )

    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException, match="object required"
    ):
        service.get_type().dispatch(service, FakeDispatchContext())

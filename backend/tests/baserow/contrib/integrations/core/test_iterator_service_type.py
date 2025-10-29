import pytest

from baserow.test_utils.helpers import AnyStr
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.mark.django_db
def test_core_iterator_service_type_dispatch_data_simple_value(data_fixture):
    service = data_fixture.create_core_iterator_service(source="get('test')")

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    dispatch_result = service_type.dispatch(service, dispatch_context)

    assert dispatch_result.data == {"results": [2], "has_next_page": False}


@pytest.mark.django_db
def test_core_iterator_service_type_dispatch_data_array(data_fixture):
    service = data_fixture.create_core_iterator_service(source="get('array')")

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={"array": [{"test": "data"}, {"test": "data2"}]}
    )

    dispatch_result = service_type.dispatch(service, dispatch_context)

    assert dispatch_result.data == {
        "results": [{"test": "data"}, {"test": "data2"}],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_core_iterator_service_type_schema(data_fixture):
    service = data_fixture.create_core_iterator_service(
        sample_data={
            "data": {
                "results": [{"test": "data"}, {"test": "data2"}],
                "has_next_page": False,
            }
        }
    )

    service_type = service.get_type()
    assert service_type.generate_schema(service) == {
        "$schema": AnyStr(),
        "title": AnyStr(),
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"test": {"type": "string"}},
            "required": ["test"],
        },
    }


@pytest.mark.django_db
def test_core_iterator_service_types_simple_schema(data_fixture):
    service = data_fixture.create_core_iterator_service(
        sample_data={"data": {"results": ["string"]}}
    )

    service_type = service.get_type()
    assert service_type.generate_schema(service) == {
        "$schema": AnyStr(),
        "title": AnyStr(),
        "type": "array",
        "items": {
            "type": "string",
        },
    }


@pytest.mark.django_db
def test_core_iterator_service_type_empty_schema(data_fixture):
    service = data_fixture.create_core_iterator_service(
        sample_data={"data": {"results": []}}
    )

    service_type = service.get_type()
    assert service_type.generate_schema(service) is None

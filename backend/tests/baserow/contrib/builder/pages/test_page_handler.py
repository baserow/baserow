import pytest

from baserow.contrib.builder.elements.models import ColumnElement, TextElement
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.pages.constants import ILLEGAL_PATH_SAMPLE_CHARACTER
from baserow.contrib.builder.pages.exceptions import (
    DuplicatePathParamsInPath,
    PageDoesNotExist,
    PageNameNotUnique,
    PageNotInBuilder,
    PagePathNotUnique,
    PathParamNotDefined,
    PathParamNotInPath,
    SharedPageIsReadOnly,
)
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page


@pytest.mark.django_db
def test_get_page(data_fixture):
    page = data_fixture.create_builder_page()
    assert PageHandler().get_page(page.id).id == page.id


@pytest.mark.django_db
def test_get_page_page_does_not_exist(data_fixture):
    with pytest.raises(PageDoesNotExist):
        PageHandler().get_page(9999)


@pytest.mark.django_db
def test_get_page_base_queryset(data_fixture, django_assert_num_queries):
    page = data_fixture.create_builder_page()

    # With selecting related
    base_queryset = Page.objects.exclude(id=page.id)

    with pytest.raises(PageDoesNotExist):
        PageHandler().get_page(page.id, base_queryset=base_queryset)


@pytest.mark.django_db
def test_create_page(data_fixture):
    builder = data_fixture.create_builder_application()
    expected_order = Page.get_last_order(builder)

    page = PageHandler().create_page(builder, "test", path="/test")

    assert page.order == expected_order
    assert page.name == "test"


@pytest.mark.django_db
def test_create_page_page_name_not_unique(data_fixture):
    page = data_fixture.create_builder_page(name="test", path="/test")

    with pytest.raises(PageNameNotUnique):
        PageHandler().create_page(page.builder, name="test", path="/new")


@pytest.mark.django_db
def test_create_page_page_path_not_unique(data_fixture):
    page = data_fixture.create_builder_page(path="/test/test")

    with pytest.raises(PagePathNotUnique):
        PageHandler().create_page(page.builder, name="test", path="/test/test")


@pytest.mark.django_db
def test_create_page_duplicate_params_in_path(data_fixture):
    builder = data_fixture.create_builder_application()

    with pytest.raises(DuplicatePathParamsInPath):
        PageHandler().create_page(
            builder,
            name="test",
            path="/test/:test/:test",
            path_params=[{"name": "test", "param_type": "text"}],
        )


@pytest.mark.django_db
def test_delete_page(data_fixture):
    page = data_fixture.create_builder_page()

    previous_count = Page.objects.count()

    PageHandler().delete_page(page)

    assert Page.objects.count() == previous_count - 1


@pytest.mark.django_db
def test_delete_shared_page(data_fixture):
    page = data_fixture.create_builder_page()
    shared_page = page.builder.shared_page

    with pytest.raises(SharedPageIsReadOnly):
        PageHandler().delete_page(shared_page)


@pytest.mark.django_db
def test_update_page(data_fixture):
    page = data_fixture.create_builder_page(name="test")

    PageHandler().update_page(page, name="new")

    page.refresh_from_db()

    assert page.name == "new"


@pytest.mark.django_db
def test_update_shared_page(data_fixture):
    page = data_fixture.create_builder_page(name="test")
    shared_page = page.builder.shared_page

    with pytest.raises(SharedPageIsReadOnly):
        PageHandler().update_page(shared_page, name="new")


@pytest.mark.django_db
def test_update_page_page_name_not_unique(data_fixture):
    page = data_fixture.create_builder_page(name="test")
    page_two = data_fixture.create_builder_page(builder=page.builder, name="test2")

    with pytest.raises(PageNameNotUnique):
        PageHandler().update_page(page_two, name=page.name)


@pytest.mark.django_db
def test_update_page_page_path_not_unique(data_fixture):
    page = data_fixture.create_builder_page()
    page_two = data_fixture.create_builder_page(builder=page.builder)

    with pytest.raises(PagePathNotUnique):
        PageHandler().update_page(page_two, path=page.path)


@pytest.mark.django_db
def test_order_pages(data_fixture):
    builder = data_fixture.create_builder_application()
    page_one = data_fixture.create_builder_page(builder=builder, order=10)
    page_two = data_fixture.create_builder_page(builder=builder, order=20)

    assert PageHandler().order_pages(builder, [page_two.id, page_one.id]) == [
        page_two.id,
        page_one.id,
    ]

    page_one.refresh_from_db()
    page_two.refresh_from_db()

    assert page_one.order > page_two.order


@pytest.mark.django_db
def test_order_pages_page_not_in_builder(data_fixture):
    builder = data_fixture.create_builder_application()
    shared_page = builder.shared_page
    page_one = data_fixture.create_builder_page(builder=builder, order=1)
    page_two = data_fixture.create_builder_page(builder=builder, order=2)

    base_qs = Page.objects.filter(id=page_two.id)

    with pytest.raises(PageNotInBuilder):
        PageHandler().order_pages(builder, [page_two.id, page_one.id], base_qs=base_qs)

    # We can't order shared page
    with pytest.raises(PageNotInBuilder):
        PageHandler().order_pages(builder, [page_two.id, shared_page.id])


@pytest.mark.django_db
def test_duplicate_page(data_fixture):
    page = data_fixture.create_builder_page()

    previous_count = Page.objects.count()

    page_clone = PageHandler().duplicate_page(page)

    assert Page.objects.count() == previous_count + 1
    assert page_clone.id != page.id
    assert page_clone.name != page.name
    assert page_clone.order != page.order


@pytest.mark.django_db
def test_duplicate_shared_page(data_fixture):
    page = data_fixture.create_builder_page()
    shared_page = page.builder.shared_page

    with pytest.raises(SharedPageIsReadOnly):
        PageHandler().duplicate_page(shared_page)


def test_is_page_path_valid():
    assert PageHandler().is_page_path_valid("test/", []) is True
    assert PageHandler().is_page_path_valid("test/:id", []) is False
    assert (
        PageHandler().is_page_path_valid(
            "test/", [{"name": "id", "param_type": "text"}]
        )
        is False
    )
    assert (
        PageHandler().is_page_path_valid(
            "test/:", [{"name": "id", "param_type": "text"}]
        )
        is False
    )
    assert PageHandler().is_page_path_valid("test/:", {}) is True
    assert (
        PageHandler().is_page_path_valid(
            "test/::id", [{"name": "id", "param_type": "text"}]
        )
        is True
    )
    assert (
        PageHandler().is_page_path_valid(
            "product/:id-:slug",
            [
                {"name": "id", "param_type": "text"},
                {"name": "slug", "param_type": "text"},
            ],
        )
        is True
    )
    assert (
        PageHandler().is_page_path_valid(
            "product/:test/:test", [{"name": "test", "param_type": "text"}]
        )
        is False
    )


def test_is_page_path_valid_raises():
    with pytest.raises(PathParamNotInPath):
        PageHandler().is_page_path_valid(
            "test", [{"name": "id", "param_type": "text"}], raises=True
        )

    with pytest.raises(PathParamNotDefined):
        PageHandler().is_page_path_valid("test/:id", [], raises=True)


@pytest.mark.django_db
def test_find_unused_page_path(data_fixture):
    page = data_fixture.create_builder_page(path="/test")

    assert PageHandler().find_unused_page_path(page.builder, "/test") == "/test/2"


@pytest.mark.django_db
def test_is_page_path_unique(data_fixture):
    builder = data_fixture.create_builder_application()

    data_fixture.create_builder_page(builder=builder, path="/test/:id")

    assert PageHandler().is_page_path_unique(builder, "/new") is True
    assert PageHandler().is_page_path_unique(builder, "/test/:id") is False
    assert PageHandler().is_page_path_unique(builder, "/test/:id/:hello") is True
    assert PageHandler().is_page_path_unique(builder, "/test/:id-:hello") is True


@pytest.mark.django_db
def test_is_page_path_unique_different_param_position(data_fixture):
    builder = data_fixture.create_builder_application()

    data_fixture.create_builder_page(builder=builder, path="/test/:id/hello/:new")

    assert PageHandler().is_page_path_unique(builder, "/test/:new/hello/:id") is False
    assert PageHandler().is_page_path_unique(builder, "/test/:new/:id/hello") is True


@pytest.mark.django_db
def test_is_page_path_unique_raises(data_fixture):
    builder = data_fixture.create_builder_application()

    data_fixture.create_builder_page(builder=builder, path="/test/:id")

    with pytest.raises(PagePathNotUnique):
        PageHandler().is_page_path_unique(builder, "/test/:id", raises=True)


def test_generalise_path():
    assert PageHandler().generalise_path("/test") == "/test"
    assert (
        PageHandler().generalise_path("/test/:id")
        == f"/test/{ILLEGAL_PATH_SAMPLE_CHARACTER}"
    )
    assert (
        PageHandler().generalise_path("/test/:id/hello/:test")
        == f"/test/{ILLEGAL_PATH_SAMPLE_CHARACTER}/hello/{ILLEGAL_PATH_SAMPLE_CHARACTER}"
    )
    assert (
        PageHandler().generalise_path("/test/:id-:hello")
        == f"/test/{ILLEGAL_PATH_SAMPLE_CHARACTER}-{ILLEGAL_PATH_SAMPLE_CHARACTER}"
    )


@pytest.mark.django_db
def test_import_element(data_fixture):
    element = data_fixture.create_builder_text_element(value="'test'")
    element_type = element_type_registry.get_by_model(element)
    element_serialized = element_type.export_serialized(element)
    new_page = data_fixture.create_builder_page(builder=element.page.builder)

    elements_imported = PageHandler().import_elements(
        new_page,
        [element_serialized],
        {},
    )

    assert len(elements_imported) == 1
    assert elements_imported[0].id != element.id
    assert elements_imported[0].specific.value == element.value


@pytest.mark.django_db
def test_import_element_has_to_import_parent_first(data_fixture):
    page = data_fixture.create_builder_page()
    parent_column = data_fixture.create_builder_column_element(
        page=page, column_amount=15
    )
    text_element = data_fixture.create_builder_text_element(
        page=page, parent_element=parent_column
    )
    parent_serialized = element_type_registry.get_by_model(
        parent_column
    ).export_serialized(parent_column)
    element_serialized = element_type_registry.get_by_model(
        text_element
    ).export_serialized(text_element)
    new_page = data_fixture.create_builder_page(builder=text_element.page.builder)

    [imported_column, imported_text] = PageHandler().import_elements(
        new_page,
        [parent_serialized, element_serialized],
        {},
    )

    assert isinstance(imported_column, ColumnElement)
    assert isinstance(imported_text, TextElement)

    assert imported_text.parent_element_id != text_element.parent_element_id
    assert imported_text.parent_element_id == imported_column.id


@pytest.mark.django_db
def test_import_element_has_to_instance_already_created(data_fixture):
    page = data_fixture.create_builder_page()
    parent_column = data_fixture.create_builder_column_element(
        page=page, column_amount=15
    )
    text_element = data_fixture.create_builder_text_element(
        page=page, parent_element=parent_column
    )
    parent_serialized = element_type_registry.get_by_model(
        parent_column
    ).export_serialized(parent_column)
    element_serialized = element_type_registry.get_by_model(
        text_element
    ).export_serialized(text_element)
    new_page = data_fixture.create_builder_page(builder=text_element.page.builder)

    [imported_column, imported_text] = PageHandler().import_elements(
        new_page,
        [element_serialized, parent_serialized],
        {},
    )

    assert isinstance(imported_column, ColumnElement)
    assert isinstance(imported_text, TextElement)

    assert imported_text.parent_element_id != text_element.parent_element_id
    assert imported_text.parent_element_id == imported_column.id

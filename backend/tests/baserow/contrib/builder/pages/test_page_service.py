from unittest.mock import patch

import pytest

from baserow.contrib.builder.pages.exceptions import PageNotInBuilder
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.service import PageService
from baserow.core.exceptions import UserNotInWorkspace


@patch("baserow.contrib.builder.pages.service.page_created")
@pytest.mark.django_db
def test_page_created_signal_sent(page_created_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    page_service = PageService()
    page = page_service.create_page(user, builder, "test", "/test")

    page_created_mock.send.assert_called_once_with(page_service, page=page, user=user)


@pytest.mark.django_db
def test_create_page_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()

    with pytest.raises(UserNotInWorkspace):
        PageService().create_page(user, builder, "test", "/test")


@patch("baserow.contrib.builder.pages.service.page_deleted")
@pytest.mark.django_db
def test_page_deleted_signal_sent(page_deleted_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)
    page_id = page.id

    page_service = PageService()
    page_service.delete_page(user, page)

    page_deleted_mock.send.assert_called_once_with(
        page_service, builder=builder, page_id=page_id, user=user
    )


@pytest.mark.django_db(transaction=True)
def test_delete_page_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    user_unrelated = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    page = PageService().create_page(user, builder, "test", "/test")

    previous_count = Page.objects.count()

    with pytest.raises(UserNotInWorkspace):
        PageService().delete_page(user_unrelated, page)

    assert Page.objects.count() == previous_count


@pytest.mark.django_db
def test_get_page_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()
    page = data_fixture.create_builder_page(builder=builder)

    with pytest.raises(UserNotInWorkspace):
        PageService().get_page(user, page.id)


@patch("baserow.contrib.builder.pages.service.page_updated")
@pytest.mark.django_db
def test_page_updated_signal_sent(page_updated_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)

    page_service = PageService()
    page_service.update_page(user, page, name="new")

    page_updated_mock.send.assert_called_once_with(page_service, page=page, user=user)


@pytest.mark.django_db
def test_update_page_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()
    page = data_fixture.create_builder_page(builder=builder)

    with pytest.raises(UserNotInWorkspace):
        PageService().update_page(user, page, name="test")


@pytest.mark.django_db
def test_update_page_invalid_values(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)

    page_updated = PageService().update_page(user, page, nonsense="hello")

    assert hasattr(page_updated, "nonsense") is False


@patch("baserow.contrib.builder.pages.service.pages_reordered")
@pytest.mark.django_db
def test_pages_reordered_signal_sent(pages_reordered_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page_one = data_fixture.create_builder_page(builder=builder, order=1)
    page_two = data_fixture.create_builder_page(builder=builder, order=2)

    page_service = PageService()
    full_order = page_service.order_pages(user, builder, [page_two.id, page_one.id])

    pages_reordered_mock.send.assert_called_once_with(
        page_service, builder=builder, order=full_order, user=user
    )


@pytest.mark.django_db
def test_order_pages_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()
    page_one = data_fixture.create_builder_page(builder=builder, order=1)
    page_two = data_fixture.create_builder_page(builder=builder, order=2)

    with pytest.raises(UserNotInWorkspace):
        PageService().order_pages(user, builder, [page_two.id, page_one.id])


@pytest.mark.django_db
def test_order_pages_page_not_in_builder(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page_one = data_fixture.create_builder_page(builder=builder, order=1)
    page_two = data_fixture.create_builder_page(order=2)

    with pytest.raises(PageNotInBuilder):
        PageService().order_pages(user, builder, [page_two.id, page_one.id])


@pytest.mark.django_db
def test_duplicate_page(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)

    page_clone = PageService().duplicate_page(user, page)

    assert page_clone.order != page.order
    assert page_clone.id != page.id
    assert page_clone.name != page.name


@pytest.mark.django_db
def test_duplicate_page_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page()

    with pytest.raises(UserNotInWorkspace):
        PageService().duplicate_page(user, page)

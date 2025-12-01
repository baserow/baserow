import pytest

from baserow.contrib.builder.elements.usage_types import (
    ImageElementWorkspaceStorageUsageItem,
)
from baserow.core.usage.registries import USAGE_UNIT_MB


@pytest.mark.django_db
def test_image_element_workspace_storage_usage_item(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    usage_in_mb = (
        ImageElementWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_mb == 0

    image_file = data_fixture.create_user_file(is_image=True, size=2 * USAGE_UNIT_MB)

    data_fixture.create_builder_image_element(
        page=page,
        image_file=image_file,
    )

    usage_in_mb = (
        ImageElementWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
            workspace.id
        )
    )

    assert usage_in_mb == 2


@pytest.mark.django_db
def test_image_element_workspace_storage_usage_item_trashed_builder(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    image_file = data_fixture.create_user_file(is_image=True, size=2 * USAGE_UNIT_MB)

    data_fixture.create_builder_image_element(
        page=page,
        image_file=image_file,
    )

    usage = ImageElementWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 2

    builder.trashed = True
    builder.save()
    usage = ImageElementWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )
    assert usage == 0


@pytest.mark.django_db
def test_image_element_workspace_storage_usage_item_trashed_page(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    image_file = data_fixture.create_user_file(is_image=True, size=2 * USAGE_UNIT_MB)

    data_fixture.create_builder_image_element(
        page=page,
        image_file=image_file,
    )

    usage = ImageElementWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 2

    page.trashed = True
    page.save()
    usage = ImageElementWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )
    assert usage == 0


@pytest.mark.django_db
def test_image_element_workspace_storage_usage_item_duplicate_ids(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    image_file = data_fixture.create_user_file(is_image=True, size=2 * USAGE_UNIT_MB)

    data_fixture.create_builder_image_element(
        page=page,
        image_file=image_file,
    )

    usage = ImageElementWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 2

    data_fixture.create_builder_image_element(
        page=page,
        image_file=image_file,
    )

    usage = ImageElementWorkspaceStorageUsageItem().calculate_storage_usage_workspace(
        workspace.id
    )

    assert usage == 2

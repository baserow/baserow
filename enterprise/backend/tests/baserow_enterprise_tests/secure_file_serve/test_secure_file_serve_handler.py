from unittest import mock
from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.core.signing import SignatureExpired
from django.test import override_settings

import pytest

from baserow.core.context import clear_current_workspace_id, set_current_workspace_id
from baserow_enterprise.secure_file_serve.constants import SecureFileServePermission
from baserow_enterprise.secure_file_serve.exceptions import SecureFileServeException
from baserow_enterprise.secure_file_serve.handler import (
    SecureFile,
    SecureFileServeHandler,
)
from baserow_enterprise.secure_file_serve.storage import (
    EnterpriseFileStorage,
    SecureFileServeSignerPayload,
)


@pytest.fixture(autouse=True)
def clear_context():
    yield
    clear_current_workspace_id()


def test_secure_file_handler_unsign_data_invalid_payload():
    for payload in [None, "", "invalid_payload"]:
        handler = SecureFileServeHandler()

        with pytest.raises(SecureFileServeException) as error:
            handler.unsign_data(signed_path=payload)
            assert str(error.value) == "Invalid signature"


@mock.patch("baserow_enterprise.secure_file_serve.handler.EnterpriseFileStorage")
def test_secure_file_handler_unsign_data_expired_payload(mocked_storage):
    mocked_storage.unsign_data.side_effect = SignatureExpired()

    handler = SecureFileServeHandler()
    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with pytest.raises(SecureFileServeException) as error:
        handler.unsign_data(signed_path=signed_data)
        assert str(error.value) == "File expired"


def test_secure_file_handler_unsign_valid_data():
    handler = SecureFileServeHandler()
    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")
    expected_payload = SecureFileServeSignerPayload(
        name="path/to/file.txt", workspace_id=None
    )

    payload = handler.unsign_data(signed_path=signed_data)
    assert payload == expected_payload


def test_secure_file_handler_get_file_path_exists():
    handler = SecureFileServeHandler()

    data = SecureFileServeSignerPayload(name="path/to/file.txt", workspace_id=None)
    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        file_path = handler.get_file_path(data=data)
        assert file_path == data.name


def test_secure_file_handler_get_file_path_does_not_exist():
    handler = SecureFileServeHandler()

    data = SecureFileServeSignerPayload(name="path/to/file.txt", workspace_id=None)

    with mock.patch(
        "baserow.core.storage.get_default_storage"
    ) as mocked_default_storage:
        mocked_default_storage.exists.return_value = False
        with pytest.raises(SecureFileServeException) as error:
            handler.get_file_path(data=data)
            assert str(error.value) == "File not found"


def test_secure_file_handler_get_file_name():
    handler = SecureFileServeHandler()

    scenarios = [
        (None, ""),
        ("", ""),
        ("path/to/file.txt", "file.txt"),
        ("file.txt", "file.txt"),
    ]

    for given_path, expected_name in scenarios:
        assert handler.get_file_name(given_path) == expected_name


def test_secure_file_handler_extract_file_info_or_raise_invalid_payload():
    handler = SecureFileServeHandler()

    with pytest.raises(SecureFileServeException) as error:
        handler.extract_file_info_or_raise(user=AnonymousUser(), signed_data="")
        assert str(error.value) == "Invalid signature"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.DISABLED
)
def test_secure_file_handler_extract_file_info_or_raise_non_existing_file():
    handler = SecureFileServeHandler()

    with mock.patch(
        "baserow.core.storage.get_default_storage"
    ) as mocked_default_storage:
        mocked_default_storage.exists.return_value = False

        with pytest.raises(SecureFileServeException) as error:
            handler.extract_file_info_or_raise(user=AnonymousUser(), signed_data="")
            assert str(error.value) == "File not found"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.DISABLED,
)
def test_secure_file_handler_extract_file_info_or_raise_valid_data_disabled_permission_check():
    handler = SecureFileServeHandler()

    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        secure_file = handler.extract_file_info_or_raise(
            user=AnonymousUser(), signed_data=signed_data
        )
        assert isinstance(secure_file, SecureFile)
        assert secure_file.name == "file.txt"
        assert secure_file.path == "path/to/file.txt"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.SIGNED_IN,
)
def test_secure_file_handler_extract_file_info_or_raise_valid_data_signed_in_with_anonymous():
    handler = SecureFileServeHandler()

    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        with pytest.raises(SecureFileServeException) as error:
            handler.extract_file_info_or_raise(
                user=AnonymousUser(), signed_data=signed_data
            )
            assert str(error.value) == "User is not authenticated"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.SIGNED_IN,
)
def test_secure_file_handler_extract_file_info_or_raise_valid_data_signed_in_with_authenticated(
    data_fixture,
):
    user = data_fixture.create_user()

    handler = SecureFileServeHandler()

    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        secure_file = handler.extract_file_info_or_raise(
            user=user, signed_data=signed_data
        )
        assert isinstance(secure_file, SecureFile)
        assert secure_file.name == "file.txt"
        assert secure_file.path == "path/to/file.txt"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
)
def test_secure_file_handler_extract_file_info_or_raise_valid_data_workspace_with_anonymous():
    handler = SecureFileServeHandler()

    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        with pytest.raises(SecureFileServeException) as error:
            handler.extract_file_info_or_raise(
                user=AnonymousUser(), signed_data=signed_data
            )
            assert str(error.value) == "User is not authenticated"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
)
def test_secure_file_handler_extract_file_info_or_raise_valid_data_workspace_wrong_workspace(
    data_fixture,
):
    user_1 = data_fixture.create_user()

    user_2 = data_fixture.create_user()
    workspace_2 = data_fixture.create_workspace(user=user_2)

    set_current_workspace_id(workspace_2.id)
    handler = SecureFileServeHandler()

    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        with pytest.raises(SecureFileServeException) as error:
            handler.extract_file_info_or_raise(user=user_1, signed_data=signed_data)
            assert str(error.value) == "Can't access file"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
)
def test_secure_file_handler_extract_file_info_or_raise_valid_data_workspace_with_valid_user(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    set_current_workspace_id(workspace.id)

    handler = SecureFileServeHandler()

    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        secure_file = handler.extract_file_info_or_raise(
            user=user, signed_data=signed_data
        )
        assert isinstance(secure_file, SecureFile)
        assert secure_file.name == "file.txt"
        assert secure_file.path == "path/to/file.txt"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
)
def test_secure_file_handler_extract_file_info_or_raise_staff_user_no_workspace(
    data_fixture,
):
    user = data_fixture.create_user(is_staff=True)

    handler = SecureFileServeHandler()

    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        secure_file = handler.extract_file_info_or_raise(
            user=user, signed_data=signed_data
        )
        assert isinstance(secure_file, SecureFile)
        assert secure_file.name == "file.txt"
        assert secure_file.path == "path/to/file.txt"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
)
def test_secure_file_handler_extract_file_info_or_raise_staff_user_within_own_workspace(
    data_fixture,
):
    user = data_fixture.create_user(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)
    set_current_workspace_id(workspace.id)

    handler = SecureFileServeHandler()

    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        secure_file = handler.extract_file_info_or_raise(
            user=user, signed_data=signed_data
        )
        assert isinstance(secure_file, SecureFile)
        assert secure_file.name == "file.txt"
        assert secure_file.path == "path/to/file.txt"


@pytest.mark.django_db
@override_settings(
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
)
def test_secure_file_handler_extract_file_info_or_raise_staff_user_outside_own_workspace(
    data_fixture,
):
    user_1 = data_fixture.create_user(is_staff=True)
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user_2)
    set_current_workspace_id(workspace.id)

    handler = SecureFileServeHandler()

    storage = EnterpriseFileStorage()
    signed_data = storage.sign_data(name="path/to/file.txt")

    with mock.patch(
        "baserow_enterprise.secure_file_serve.handler.get_default_storage"
    ) as get_storage_mock:
        storage_mock = MagicMock()
        storage_mock.exists.return_value = True

        get_storage_mock.return_value = storage_mock

        with pytest.raises(SecureFileServeException) as error:
            handler.extract_file_info_or_raise(user=user_1, signed_data=signed_data)
            assert str(error.value) == "Can't access file"

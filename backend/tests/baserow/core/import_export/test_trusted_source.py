import pytest
from loguru import logger

from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import ImportExportTrustedSource

SAMPLE_B64_PUBLIC_KEY = (
    "LS0tLS1CRUdJTiBSU0EgUFVCTElDIEtFWS0tLS0tCk1JSUJpZ0tDQVlFQXZtcTc3UHRmclpPbXB"
    "MQnFoSkZOVkdFMXdGYURPTmlLdnJhOE5ORWhMOWo1aFUzc0o4NFgKcmJpS3JMeFVES1R4ckFKaz"
    "J1VFdzOEwrd1k3T2puS1ZLNXlHTmhWYTFiNHZpaXJraVlwYlhncHdwc2FKekl0RwpTVTlZZ3J0a"
    "VBZTGhnRGYxQmtsbHZBTmVBOU80ZDRqNTR5dzVSK0JrYXNMVy9DMWptSUpiRWRuaFJ5QlM1SE41"
    "CmFkdzd1QlE1SzBUWGkzcVBFaXo3KzZtUURXanB5VkV5V3RLSnBqQmtHcXZGNXlhU05ibi9rMEc"
    "yWnhaU1ZiSHQKYTA5eHlPZDZOV0VUVWtmTzdYcGl3NWlTWG0yUm9LeU5IT2VPK3hQSjdDREFxcj"
    "B6MkwwQXlVaDJDZVhhNURtUwo2cGpCZjlmUGRJcnhNNCt2L1lBSUdSWkE3NFBGZllkd1RteHlrY"
    "01nQVhtcWlLaWx4SjNwbVZVWDlPZ3lnMFlOCnN4OHE0ejhNcHBIL0dJRjJLVlhsMW5CcXd3b1lZ"
    "TGJHN1crM2MycjA4NmtGa2RzVEhnVkRoc0tNNUM0NURGdkMKNmFaTkkwS2VtcHZPOXpUaVMxQ3h"
    "kM0xKbHhLQU9haCt4eUFaWkUwbm42cWFvKzFQYWN6YWlTOGVmd3c0VjVudApVVzNYVDRZYTUweG"
    "hBZ01CQUFFPQotLS0tLUVORCBSU0EgUFVCTElDIEtFWS0tLS0t"
)


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_add_invalid_public_key_fails(data_fixture, mocker):
    mock_logger_error = mocker.patch.object(logger, "error")

    ImportExportHandler().add_trusted_public_key("test #1", "Some invalid key")

    log_messages = [args[0] for args, _ in mock_logger_error.call_args_list]
    assert any(
        "Provided public key is invalid or in wrong format" in message
        for message in log_messages
    )

    assert not ImportExportTrustedSource.objects.filter(name="test #1").exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_add_valid_public_key(data_fixture, mocker):
    mock_logger_error = mocker.patch.object(logger, "error")
    mock_logger_warning = mocker.patch.object(logger, "warning")

    ImportExportHandler().add_trusted_public_key("test #1", SAMPLE_B64_PUBLIC_KEY)

    mock_logger_error.assert_not_called()
    mock_logger_warning.assert_not_called()

    assert ImportExportTrustedSource.objects.filter(name="test #1").exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_add_duplicated_public_key_fails(data_fixture, mocker):
    mock_logger_error = mocker.patch.object(logger, "error")
    mock_logger_warning = mocker.patch.object(logger, "warning")

    ImportExportHandler().add_trusted_public_key("test #1", SAMPLE_B64_PUBLIC_KEY)
    ImportExportHandler().add_trusted_public_key("test #1", SAMPLE_B64_PUBLIC_KEY)

    mock_logger_error.assert_not_called()

    source = ImportExportTrustedSource.objects.get(name="test #1")

    log_messages = [args[0] for args, _ in mock_logger_warning.call_args_list]
    assert (
        f"Key with that public key already exists with ID #{source.id}" in log_messages
    )


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_remove_private_key_fails(data_fixture, mocker):
    source = data_fixture.create_import_export_trusted_source()

    mock_logger_error = mocker.patch.object(logger, "error")
    mock_logger_warning = mocker.patch.object(logger, "warning")

    ImportExportHandler().delete_trusted_public_key(source_id=source.id)

    mock_logger_error.assert_not_called()
    log_messages = [args[0] for args, _ in mock_logger_warning.call_args_list]
    assert "Trusted source cannot be removed as it has a private key" in log_messages


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_remove_public_key(data_fixture, mocker):
    ImportExportHandler().add_trusted_public_key("test #1", SAMPLE_B64_PUBLIC_KEY)

    source = ImportExportTrustedSource.objects.get(name="test #1")

    mock_logger_error = mocker.patch.object(logger, "error")
    mock_logger_warning = mocker.patch.object(logger, "warning")

    ImportExportHandler().delete_trusted_public_key(source_id=source.id)

    mock_logger_error.assert_not_called()
    mock_logger_warning.assert_not_called()

    assert not ImportExportTrustedSource.objects.filter(name="test #1").exists()

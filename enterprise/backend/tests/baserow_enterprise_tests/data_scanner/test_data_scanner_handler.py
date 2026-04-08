from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test.utils import override_settings
from django.utils import timezone

import pytest

from baserow_enterprise.data_scanner.exceptions import (
    DataScanDoesNotExist,
    DataScanIsAlreadyRunning,
)
from baserow_enterprise.data_scanner.handler import (
    DataScannerHandler,
    _build_broad_token_regex,
    _pattern_has_special_chars,
    convert_pattern_to_regex,
)

# _build_broad_token_regex and _pattern_has_special_chars are still used as
# internal helpers in the handler. They are imported here for unit testing.
from baserow_enterprise.data_scanner.models import (
    DataScan,
    DataScanListItem,
    DataScanResult,
)
from baserow_premium.license.exceptions import FeaturesNotAvailableError


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_alpha_token():
    assert convert_pattern_to_regex("A") == "[A-Za-z]"
    assert convert_pattern_to_regex("AA") == "[A-Za-z][A-Za-z]"


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_digit_token():
    assert convert_pattern_to_regex("D") == "[0-9]"
    assert convert_pattern_to_regex("DD") == "[0-9][0-9]"


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_any_char_token():
    assert convert_pattern_to_regex("X") == "."
    assert convert_pattern_to_regex("XX") == ".."


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_escaped_literals():
    assert convert_pattern_to_regex("\\N\\L") == "NL"
    assert convert_pattern_to_regex("\\-") == "\\-"
    assert convert_pattern_to_regex("\\.") == "\\."
    assert convert_pattern_to_regex("\\D") == "D"


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_mixed():
    assert convert_pattern_to_regex("AADD") == "[A-Za-z][A-Za-z][0-9][0-9]"
    assert (
        convert_pattern_to_regex("AA\\-DD\\-AA")
        == "[A-Za-z][A-Za-z]\\-[0-9][0-9]\\-[A-Za-z][A-Za-z]"
    )


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_iban_pattern():
    assert (
        convert_pattern_to_regex("AADDAAAADDDDDDDDDD")
        == "[A-Za-z][A-Za-z][0-9][0-9][A-Za-z][A-Za-z][A-Za-z][A-Za-z]"
        "[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]"
    )


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_dutch_iban_with_literals():
    assert (
        convert_pattern_to_regex("\\N\\LDDAAAADDDDDDDDDD")
        == "NL[0-9][0-9][A-Za-z][A-Za-z][A-Za-z][A-Za-z]"
        "[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]"
    )


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_empty():
    assert convert_pattern_to_regex("") == ""


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_trailing_backslash():
    # A trailing backslash with nothing after it is treated as a literal backslash
    assert convert_pattern_to_regex("A\\") == "[A-Za-z]\\\\"


@pytest.mark.data_scanner
def test_pattern_has_special_chars():
    assert _pattern_has_special_chars("DDDD\\-DD\\-DD") is True
    assert _pattern_has_special_chars("DDDD\\.DD") is True
    assert _pattern_has_special_chars("AADDDD") is False
    assert _pattern_has_special_chars("\\N\\LDDAAAADDDDDDDDDD") is False
    assert _pattern_has_special_chars("\\N\\L\\-DD") is True


@pytest.mark.data_scanner
def test_build_broad_token_regex():
    # For DDDD-DD-DD, the longest token fragment is DDDD -> [0-9]{4 chars}
    broad = _build_broad_token_regex("DDDD\\-DD\\-DD")
    assert broad == "[0-9][0-9][0-9][0-9]"

    # For AA.DD, the longest is AA -> [A-Za-z][A-Za-z]
    broad = _build_broad_token_regex("AA\\.DD")
    assert broad == "[A-Za-z][A-Za-z]"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_pattern(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="IBAN Scanner",
        scan_type="pattern",
        pattern="AADDAAAADDDDDDDDDD",
        frequency="daily",
    )

    assert scan.name == "IBAN Scanner"
    assert scan.scan_type == "pattern"
    assert scan.pattern == "AADDAAAADDDDDDDDDD"
    assert scan.frequency == "daily"
    assert scan.scan_all_workspaces is True
    assert scan.created_by == user


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_list_of_values(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Blacklist Scan",
        scan_type="list_of_values",
        list_items=["value1", "value2", "value3"],
    )

    assert scan.scan_type == "list_of_values"
    assert scan.list_items.count() == 3
    assert list(scan.list_items.values_list("value", flat=True)) == [
        "value1",
        "value2",
        "value3",
    ]


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_list_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["test"]],
    )
    field = fields[0]

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Table Scan",
        scan_type="list_table",
        source_table_id=table.id,
        source_field_id=field.id,
    )

    assert scan.scan_type == "list_table"
    assert scan.source_table_id == table.id
    assert scan.source_field_id == field.id


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_with_specific_workspaces(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    workspace1 = enterprise_data_fixture.create_workspace(user=user)
    workspace2 = enterprise_data_fixture.create_workspace(user=user)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Workspace Scan",
        scan_type="pattern",
        pattern="AADD",
        scan_all_workspaces=False,
        workspace_ids=[workspace1.id, workspace2.id],
    )

    assert scan.scan_all_workspaces is False
    assert set(scan.workspaces.values_list("id", flat=True)) == {
        workspace1.id,
        workspace2.id,
    }


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_all_workspaces(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="All Workspaces Scan",
        scan_type="pattern",
        pattern="99",
        scan_all_workspaces=True,
    )

    assert scan.scan_all_workspaces is True
    assert scan.workspaces.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_without_enterprise_license(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user(is_staff=True)

    with pytest.raises(FeaturesNotAvailableError):
        DataScannerHandler.create_scan(
            user=user,
            name="Test",
            scan_type="pattern",
            pattern="AA",
        )


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_scan_non_staff_user(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=False)

    with pytest.raises(PermissionDenied):
        DataScannerHandler.create_scan(
            user=user,
            name="Test",
            scan_type="pattern",
            pattern="AA",
        )


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Original",
        scan_type="pattern",
        pattern="AA",
    )

    updated = DataScannerHandler.update_scan(
        user=user,
        scan_id=scan.id,
        name="Updated",
        frequency="weekly",
        pattern="99",
    )

    assert updated.name == "Updated"
    assert updated.frequency == "weekly"
    assert updated.pattern == "99"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_without_license(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user, name="Test", scan_type="pattern", pattern="AA"
    )

    from baserow.core.cache import local_cache
    from baserow_premium.license.models import License

    License.objects.all().delete()
    local_cache.clear()

    with pytest.raises(FeaturesNotAvailableError):
        DataScannerHandler.update_scan(user=user, scan_id=scan.id, name="New")


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_non_staff(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    regular = enterprise_data_fixture.create_user(is_staff=False)

    scan = DataScannerHandler.create_scan(
        user=admin, name="Test", scan_type="pattern", pattern="AA"
    )

    with pytest.raises(PermissionDenied):
        DataScannerHandler.update_scan(user=regular, scan_id=scan.id, name="New")


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_not_found(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    with pytest.raises(DataScanDoesNotExist):
        DataScannerHandler.update_scan(user=user, scan_id=99999, name="New")


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_already_running(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Running Scan",
        scan_type="pattern",
        pattern="AA",
    )
    scan.is_running = True
    scan.save()

    with pytest.raises(DataScanIsAlreadyRunning):
        DataScannerHandler.update_scan(user=user, scan_id=scan.id, name="New Name")


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_workspaces(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    ws1 = enterprise_data_fixture.create_workspace(user=user)
    ws2 = enterprise_data_fixture.create_workspace(user=user)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Test",
        scan_type="pattern",
        pattern="AA",
        scan_all_workspaces=False,
        workspace_ids=[ws1.id],
    )
    assert set(scan.workspaces.values_list("id", flat=True)) == {ws1.id}

    updated = DataScannerHandler.update_scan(
        user=user, scan_id=scan.id, workspace_ids=[ws2.id]
    )
    assert set(updated.workspaces.values_list("id", flat=True)) == {ws2.id}


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_list_items(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="List Scan",
        scan_type="list_of_values",
        list_items=["a", "b"],
    )
    assert scan.list_items.count() == 2

    updated = DataScannerHandler.update_scan(
        user=user, scan_id=scan.id, list_items=["x", "y", "z"]
    )
    assert updated.list_items.count() == 3
    assert set(updated.list_items.values_list("value", flat=True)) == {"x", "y", "z"}


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_table_source(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table1, fields1, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Col1", "text")], rows=[["v"]]
    )
    table2, fields2, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Col2", "text")], rows=[["v"]]
    )

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Table Scan",
        scan_type="list_table",
        source_table_id=table1.id,
        source_field_id=fields1[0].id,
    )
    assert scan.source_table_id == table1.id

    DataScannerHandler.update_scan(
        user=user,
        scan_id=scan.id,
        source_table_id=table2.id,
        source_field_id=fields2[0].id,
    )
    scan.refresh_from_db()
    assert scan.source_table_id == table2.id
    assert scan.source_field_id == fields2[0].id


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_scan_clears_workspaces_when_scan_all(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    ws = enterprise_data_fixture.create_workspace(user=user)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Test",
        scan_type="pattern",
        pattern="AA",
        scan_all_workspaces=False,
        workspace_ids=[ws.id],
    )
    assert scan.workspaces.count() == 1

    DataScannerHandler.update_scan(
        user=user,
        scan_id=scan.id,
        scan_all_workspaces=True,
        workspace_ids=[ws.id],
    )
    scan.refresh_from_db()
    assert scan.workspaces.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cleanup_stale_results_on_type_change(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )

    scan = DataScannerHandler.create_scan(
        user=user, name="Test", scan_type="pattern", pattern="AA"
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="test",
        first_identified_on=now,
        last_identified_on=now,
    )
    assert scan.results.count() == 1

    DataScannerHandler.update_scan(
        user=user, scan_id=scan.id, scan_type="list_of_values", list_items=["x"]
    )
    assert scan.results.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cleanup_stale_results_on_pattern_change(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )

    scan = DataScannerHandler.create_scan(
        user=user, name="Test", scan_type="pattern", pattern="AA"
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="test",
        first_identified_on=now,
        last_identified_on=now,
    )
    assert scan.results.count() == 1

    DataScannerHandler.update_scan(user=user, scan_id=scan.id, pattern="DD")
    assert scan.results.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cleanup_stale_results_on_list_items_change(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Test",
        scan_type="list_of_values",
        list_items=["keep", "remove"],
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="keep",
        first_identified_on=now,
        last_identified_on=now,
    )
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=2,
        matched_value="remove",
        first_identified_on=now,
        last_identified_on=now,
    )
    assert scan.results.count() == 2

    DataScannerHandler.update_scan(user=user, scan_id=scan.id, list_items=["keep"])
    assert scan.results.count() == 1
    assert scan.results.first().matched_value == "keep"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cleanup_stale_results_on_empty_list(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )

    scan = DataScannerHandler.create_scan(
        user=user, name="Test", scan_type="list_of_values", list_items=["val"]
    )
    now = timezone.now()
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="val",
        first_identified_on=now,
        last_identified_on=now,
    )

    DataScannerHandler.update_scan(user=user, scan_id=scan.id, list_items=[])
    assert scan.results.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="To Delete",
        scan_type="list_of_values",
        list_items=["val1"],
    )
    scan_id = scan.id

    DataScannerHandler.delete_scan(user=user, scan_id=scan_id)

    assert DataScan.objects.filter(id=scan_id).count() == 0
    assert DataScanListItem.objects.filter(scan_id=scan_id).count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan_without_license(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user, name="Test", scan_type="pattern", pattern="AA"
    )

    from baserow.core.cache import local_cache
    from baserow_premium.license.models import License

    License.objects.all().delete()
    local_cache.clear()

    with pytest.raises(FeaturesNotAvailableError):
        DataScannerHandler.delete_scan(user=user, scan_id=scan.id)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan_non_staff(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    regular = enterprise_data_fixture.create_user(is_staff=False)

    scan = DataScannerHandler.create_scan(
        user=admin, name="Test", scan_type="pattern", pattern="AA"
    )

    with pytest.raises(PermissionDenied):
        DataScannerHandler.delete_scan(user=regular, scan_id=scan.id)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan_not_found(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    with pytest.raises(DataScanDoesNotExist):
        DataScannerHandler.delete_scan(user=user, scan_id=99999)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_scan_already_running(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Running Scan",
        scan_type="pattern",
        pattern="AA",
    )
    scan.is_running = True
    scan.save()

    with pytest.raises(DataScanIsAlreadyRunning):
        DataScannerHandler.delete_scan(user=user, scan_id=scan.id)

    # Verify the scan was not deleted.
    assert DataScan.objects.filter(id=scan.id).exists()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_scans_without_license(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user(is_staff=True)

    with pytest.raises(FeaturesNotAvailableError):
        DataScannerHandler.list_scans(user=user)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_scans_non_staff(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=False)

    with pytest.raises(PermissionDenied):
        DataScannerHandler.list_scans(user=user)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_scan(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user, name="Get Me", scan_type="pattern", pattern="AA"
    )

    fetched = DataScannerHandler.get_scan(user, scan.id)
    assert fetched.id == scan.id
    assert fetched.name == "Get Me"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_scan_not_found(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    with pytest.raises(DataScanDoesNotExist):
        DataScannerHandler.get_scan(user, 99999)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_without_license(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user(is_staff=True)

    with pytest.raises(FeaturesNotAvailableError):
        DataScannerHandler.trigger_scan(user=user, scan_id=999)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_non_staff(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    regular = enterprise_data_fixture.create_user(is_staff=False)

    scan = DataScannerHandler.create_scan(
        user=admin, name="Test", scan_type="pattern", pattern="AA"
    )

    with pytest.raises(PermissionDenied):
        DataScannerHandler.trigger_scan(user=regular, scan_id=scan.id)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_not_found(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    with pytest.raises(DataScanDoesNotExist):
        DataScannerHandler.trigger_scan(user=user, scan_id=99999)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_already_running(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Running Scan",
        scan_type="pattern",
        pattern="AA",
    )
    scan.is_running = True
    scan.save()

    with pytest.raises(DataScanIsAlreadyRunning):
        DataScannerHandler.trigger_scan(user=user, scan_id=scan.id)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trigger_scan_dispatches_task(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user, name="Test", scan_type="pattern", pattern="AA"
    )

    with patch(
        "baserow_enterprise.data_scanner.tasks.run_data_scan.delay"
    ) as mock_delay:
        DataScannerHandler.trigger_scan(user=user, scan_id=scan.id)
        mock_delay.assert_called_once_with(scan.id)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_not_found(enterprise_data_fixture):
    DataScannerHandler.run_scan(99999)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_pattern_scan(enterprise_data_fixture, populate_search_table):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Code", "text")],
        rows=[["AB12CD345678901234"], ["not matching"], ["XY99ZZ111111111111"]],
    )
    field = fields[0]

    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Pattern Test",
        scan_type="pattern",
        pattern="AADDAADDDDDDDDDDDD",
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_run_finished_at is not None
    assert scan.last_error is None or scan.last_error == ""


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_pattern_scan_dutch_iban_with_escaped_literals(
    enterprise_data_fixture, populate_search_table
):
    """
    Verifies that a pattern with escaped literal characters (e.g. \\N\\L for
    the fixed "NL" prefix) correctly matches values in the search table.
    PostgreSQL lowercases tsvector tokens, so the regex must match
    case-insensitively.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("IBAN", "text")],
        rows=[
            ["NL23INGB0007704001"],
            ["not an iban"],
            ["NL91ABNA0417164300"],
        ],
    )
    field = fields[0]

    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Dutch IBAN Scanner",
        scan_type="pattern",
        pattern="\\N\\LDDAAAADDDDDDDDDD",
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error is None or scan.last_error == ""

    results = list(
        scan.results.order_by("row_id").values_list("row_id", "matched_value")
    )
    assert len(results) == 2
    # tsvector tokens are lowercased by PostgreSQL
    assert results[0][0] == rows[0].id
    assert "nl23ingb0007704001" in results[0][1].lower()
    assert results[1][0] == rows[2].id
    assert "nl91abna0417164300" in results[1][1].lower()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_list_of_values_scan(enterprise_data_fixture, populate_search_table):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["secret123"], ["innocent"], ["secret456"]],
    )
    field = fields[0]
    workspace = table.database.workspace

    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="List of Values Test",
        scan_type="list_of_values",
        list_items=["secret123"],
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error is None or scan.last_error == ""
    assert scan.results.filter(matched_value="secret123").exists()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_without_license_records_error(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="License Test",
        scan_type="pattern",
        pattern="AA",
    )

    from baserow.core.cache import local_cache
    from baserow_premium.license.models import License

    License.objects.all().delete()
    local_cache.clear()

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert "Enterprise license no longer active" in scan.last_error


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_with_no_search_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    workspace = enterprise_data_fixture.create_workspace(user=user)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="No Search Table",
        scan_type="pattern",
        pattern="AA",
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error is None or scan.last_error == ""


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_removes_stale_results(enterprise_data_fixture):
    """Results from a previous run that are not re-identified get deleted."""

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )
    workspace = table.database.workspace

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Stale Results Test",
        scan_type="pattern",
        pattern="AA",
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )
    old_time = timezone.now() - timedelta(days=1)
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="old_match",
        first_identified_on=old_time,
        last_identified_on=old_time,
    )
    assert scan.results.count() == 1

    DataScannerHandler.run_scan(scan.id)

    assert scan.results.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_removes_result_when_cell_cleared(
    enterprise_data_fixture, populate_search_table
):
    """
    When a cell that previously matched is emptied, the next scan run should
    remove the corresponding result because it is no longer re-identified.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["secret123"], ["innocent"]],
    )
    field = fields[0]
    workspace = table.database.workspace

    search_model = populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Cell Cleared Test",
        scan_type="list_of_values",
        list_items=["secret123"],
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    # First run: the value is present, so we expect a result.
    DataScannerHandler.run_scan(scan.id)
    scan.refresh_from_db()
    assert scan.last_error is None or scan.last_error == ""
    assert scan.results.count() == 1
    assert scan.results.filter(matched_value="secret123").exists()

    # Clear the cell and remove the search table entry to simulate the user
    # emptying the cell.
    model = table.get_model()
    row = model.objects.get(id=rows[0].id)
    setattr(row, field.db_column, "")
    row.save()
    search_model.objects.filter(row_id=rows[0].id, field_id=field.id).delete()

    # Second run: the value is gone, so the stale result should be removed.
    DataScannerHandler.run_scan(scan.id)
    scan.refresh_from_db()
    assert scan.last_error is None or scan.last_error == ""
    assert scan.results.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_upsert_result_updates_existing(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )
    field = fields[0]

    scan = DataScannerHandler.create_scan(
        user=user, name="Upsert Test", scan_type="pattern", pattern="AA"
    )
    t1 = timezone.now() - timedelta(hours=1)
    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=field,
        row_id=1,
        matched_value="old",
        first_identified_on=t1,
        last_identified_on=t1,
    )

    t2 = timezone.now()
    DataScannerHandler._bulk_upsert_results(scan, [(field.id, 1, "new")], t2, set())

    result = DataScanResult.objects.get(scan=scan, row_id=1, field=field)
    assert result.matched_value == "new"
    assert result.first_identified_on == t1
    assert result.last_identified_on == t2


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_table_scan_excludes_source_table(
    enterprise_data_fixture, populate_search_table
):
    """
    When running a list_table scan, the source table itself must not appear in
    the results.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    source_table, source_fields, source_rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Keyword", "text")],
        rows=[["secret123"]],
    )
    source_field = source_fields[0]

    target_table, target_fields, target_rows = enterprise_data_fixture.build_table(
        user=user,
        database=source_table.database,
        columns=[("Notes", "text")],
        rows=[["contains secret123 inside"], ["nothing here"]],
    )
    target_field = target_fields[0]

    populate_search_table(source_table, source_field, source_rows)
    populate_search_table(target_table, target_field, target_rows)

    workspace = source_table.database.workspace
    scan = DataScannerHandler.create_scan(
        user=user,
        name="List Table Exclusion Test",
        scan_type="list_table",
        source_table_id=source_table.id,
        source_field_id=source_field.id,
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error is None or scan.last_error == ""

    results = DataScanResult.objects.filter(scan=scan)
    assert not results.filter(table=source_table).exists()
    assert results.filter(table=target_table).exists()
    target_result = results.get(table=target_table)
    assert target_result.field_id == target_field.id
    assert target_result.matched_value == "secret123"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_stale_running_scan_reset(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Stale Scan",
        scan_type="pattern",
        pattern="AA",
        frequency="daily",
    )
    scan.is_running = True
    scan.last_run_started_at = timezone.now() - timedelta(hours=7)
    scan.save()

    DataScannerHandler.check_scans_due()

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error == "Scan timed out and was automatically reset"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_check_scans_due_without_license(enterprise_data_fixture):
    """Without a license, stale scans are still reset but no new scans are dispatched."""

    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScan.objects.create(
        name="Scheduled",
        scan_type="pattern",
        pattern="AA",
        frequency="hourly",
        created_by=user,
        is_running=False,
        last_run_started_at=None,
    )

    with patch(
        "baserow_enterprise.data_scanner.tasks.run_data_scan.delay"
    ) as mock_delay:
        DataScannerHandler.check_scans_due()
        mock_delay.assert_not_called()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_check_scans_due_dispatches_scheduled_scan(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScan.objects.create(
        name="Hourly",
        scan_type="pattern",
        pattern="AA",
        frequency="hourly",
        created_by=user,
        is_running=False,
        last_run_started_at=timezone.now() - timedelta(hours=2),
    )

    with patch(
        "baserow_enterprise.data_scanner.tasks.run_data_scan.delay"
    ) as mock_delay:
        DataScannerHandler.check_scans_due()
        mock_delay.assert_called_once_with(scan.id)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_check_scans_due_skips_recently_run_scan(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    DataScan.objects.create(
        name="Recently Run",
        scan_type="pattern",
        pattern="AA",
        frequency="daily",
        created_by=user,
        is_running=False,
        last_run_started_at=timezone.now() - timedelta(hours=1),
    )

    with patch(
        "baserow_enterprise.data_scanner.tasks.run_data_scan.delay"
    ) as mock_delay:
        DataScannerHandler.check_scans_due()
        mock_delay.assert_not_called()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_check_scans_due_skips_manual_scans(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    DataScan.objects.create(
        name="Manual",
        scan_type="pattern",
        pattern="AA",
        frequency="manual",
        created_by=user,
        is_running=False,
        last_run_started_at=None,
    )

    with patch(
        "baserow_enterprise.data_scanner.tasks.run_data_scan.delay"
    ) as mock_delay:
        DataScannerHandler.check_scans_due()
        mock_delay.assert_not_called()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_check_scans_due_dispatches_never_run_scan(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScan.objects.create(
        name="Never Run",
        scan_type="pattern",
        pattern="AA",
        frequency="weekly",
        created_by=user,
        is_running=False,
        last_run_started_at=None,
    )

    with patch(
        "baserow_enterprise.data_scanner.tasks.run_data_scan.delay"
    ) as mock_delay:
        DataScannerHandler.check_scans_due()
        mock_delay.assert_called_once_with(scan.id)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_result_deleted_when_table_deleted(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["test"]],
    )

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Cascade Test",
        scan_type="pattern",
        pattern="AA",
    )

    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="test",
        first_identified_on=timezone.now(),
        last_identified_on=timezone.now(),
    )

    assert DataScanResult.objects.filter(scan=scan).count() == 1

    table.delete()

    assert DataScanResult.objects.filter(scan=scan).count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_result_deleted_when_field_deleted(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["test"]],
    )
    field = fields[0]

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Field Cascade Test",
        scan_type="pattern",
        pattern="AA",
    )

    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=field,
        row_id=1,
        matched_value="test",
        first_identified_on=timezone.now(),
        last_identified_on=timezone.now(),
    )

    assert DataScanResult.objects.filter(scan=scan).count() == 1

    field.delete()

    assert DataScanResult.objects.filter(scan=scan).count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_result_deleted_when_scan_deleted(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )

    scan = DataScannerHandler.create_scan(
        user=user, name="Test", scan_type="pattern", pattern="AA"
    )

    DataScanResult.objects.create(
        scan=scan,
        table=table,
        field=fields[0],
        row_id=1,
        matched_value="test",
        first_identified_on=timezone.now(),
        last_identified_on=timezone.now(),
    )

    scan_id = scan.id
    DataScannerHandler.delete_scan(user=user, scan_id=scan_id)
    assert DataScanResult.objects.filter(scan_id=scan_id).count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_source_table_set_null_when_table_deleted(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Table Scan",
        scan_type="list_table",
        source_table_id=table.id,
        source_field_id=fields[0].id,
    )

    assert scan.source_table_id == table.id

    table.delete()

    scan.refresh_from_db()
    assert scan.source_table is None


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_source_field_set_null_when_field_deleted(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["test"]]
    )

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Table Scan",
        scan_type="list_table",
        source_table_id=table.id,
        source_field_id=fields[0].id,
    )

    fields[0].delete()

    scan.refresh_from_db()
    assert scan.source_field is None


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_excludes_trashed_field(
    enterprise_data_fixture, populate_search_table
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["secret123"]],
    )
    field = fields[0]
    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Trashed Field Test",
        scan_type="list_of_values",
        list_items=["secret123"],
    )

    field.trashed = True
    field.save()

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.last_error is None or scan.last_error == ""
    assert scan.results.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_excludes_trashed_table(
    enterprise_data_fixture, populate_search_table
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["secret123"]],
    )
    field = fields[0]
    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Trashed Table Test",
        scan_type="list_of_values",
        list_items=["secret123"],
    )

    table.trashed = True
    table.save()

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.last_error is None or scan.last_error == ""
    assert scan.results.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_excludes_trashed_database(
    enterprise_data_fixture, populate_search_table
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["secret123"]],
    )
    field = fields[0]
    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Trashed Database Test",
        scan_type="list_of_values",
        list_items=["secret123"],
    )

    database = table.database
    database.trashed = True
    database.save()

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.last_error is None or scan.last_error == ""
    assert scan.results.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_excludes_trashed_row(enterprise_data_fixture, populate_search_table):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["secret123"], ["secret456"]],
    )
    field = fields[0]
    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Trashed Row Test",
        scan_type="list_of_values",
        list_items=["secret123", "secret456"],
    )

    model = table.get_model()
    model.objects_and_trash.filter(id=rows[0].id).update(trashed=True)

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.last_error is None or scan.last_error == ""
    # Only the second (non-trashed) row should appear.
    assert scan.results.count() == 1
    assert scan.results.filter(row_id=rows[1].id).exists()


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_excludes_trashed_workspace(
    enterprise_data_fixture, populate_search_table
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["secret123"]],
    )
    field = fields[0]
    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Trashed Workspace Test",
        scan_type="list_of_values",
        list_items=["secret123"],
    )

    workspace = table.database.workspace
    workspace.trashed = True
    workspace.save()

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.last_error is None or scan.last_error == ""
    assert scan.results.count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_pattern_scan_excludes_trashed_field(
    enterprise_data_fixture, populate_search_table
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("IBAN", "text")],
        rows=[["NL23INGB0007704001"]],
    )
    field = fields[0]
    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Pattern Trash Test",
        scan_type="pattern",
        pattern="\\N\\LDDAAAADDDDDDDDDD",
    )

    field.trashed = True
    field.save()

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.last_error is None or scan.last_error == ""
    assert scan.results.count() == 0


@pytest.mark.data_scanner
def test_convert_pattern_to_regex_special_characters():
    """
    Escaped special characters like hyphens must be preserved in the
    generated regex so that patterns like ``DDDD\\-DD\\-DD`` can match
    values such as ``2021-01-01``.
    """

    regex = convert_pattern_to_regex("DDDD\\-DD\\-DD")
    assert regex == "[0-9][0-9][0-9][0-9]\\-[0-9][0-9]\\-[0-9][0-9]"

    import re

    compiled = re.compile(regex, re.IGNORECASE)
    assert compiled.search("2021-01-01") is not None
    assert compiled.search("9999-12-31") is not None
    assert compiled.search("not a date") is None


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_pattern_scan_with_special_characters(
    enterprise_data_fixture, populate_search_table
):
    """
    A pattern containing escaped special characters (e.g. hyphens) must
    match cell values in the actual user table even though tsvector
    tokenization would strip those characters.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Date", "text")],
        rows=[
            ["2021-01-01"],
            ["not a date"],
            ["1999-12-31"],
        ],
    )
    field = fields[0]
    populate_search_table(table, field, rows)

    workspace = table.database.workspace
    scan = DataScannerHandler.create_scan(
        user=user,
        name="Date Pattern Test",
        scan_type="pattern",
        pattern="DDDD\\-DD\\-DD",
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error is None or scan.last_error == ""

    results = list(
        scan.results.order_by("row_id").values_list("row_id", "matched_value")
    )
    assert len(results) == 2
    assert results[0][0] == rows[0].id
    assert results[0][1] == "2021-01-01"
    assert results[1][0] == rows[2].id
    assert results[1][1] == "1999-12-31"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_pattern_scan_whole_words_true(
    enterprise_data_fixture, populate_search_table
):
    """
    When ``whole_words=True``, a pattern like ``DDDD`` must match ``1234``
    but not ``12345`` or ``1234test``.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Code", "text")],
        rows=[
            ["1234"],
            ["12345"],
            ["1234test"],
            ["1234 test"],
            ["test 1234 test"],
        ],
    )
    populate_search_table(table, fields[0], rows)

    workspace = table.database.workspace
    scan = DataScannerHandler.create_scan(
        user=user,
        name="Whole Words Pattern",
        scan_type="pattern",
        pattern="DDDD",
        whole_words=True,
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error is None or scan.last_error == ""

    matched_row_ids = set(scan.results.values_list("row_id", flat=True))
    assert rows[0].id in matched_row_ids  # "1234" -> match
    assert rows[1].id not in matched_row_ids  # "12345" -> no match
    assert rows[2].id not in matched_row_ids  # "1234test" -> no match
    assert rows[3].id in matched_row_ids  # "1234 test" -> match
    assert rows[4].id in matched_row_ids  # "test 1234 test" -> match


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_pattern_scan_whole_words_false(
    enterprise_data_fixture, populate_search_table
):
    """
    When ``whole_words=False``, a pattern like ``DDDD`` must also match
    ``12345`` because ``1234`` is contained within it.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Code", "text")],
        rows=[
            ["1234"],
            ["12345"],
            ["1234test"],
        ],
    )
    populate_search_table(table, fields[0], rows)

    workspace = table.database.workspace
    scan = DataScannerHandler.create_scan(
        user=user,
        name="Partial Pattern",
        scan_type="pattern",
        pattern="DDDD",
        whole_words=False,
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error is None or scan.last_error == ""

    matched_row_ids = set(scan.results.values_list("row_id", flat=True))
    assert rows[0].id in matched_row_ids  # "1234" -> match
    assert rows[1].id in matched_row_ids  # "12345" -> match (partial)
    assert rows[2].id in matched_row_ids  # "1234test" -> match (partial)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_list_scan_correct_matched_value(
    enterprise_data_fixture, populate_search_table
):
    """
    When scanning for a list of values, the matched_value must correctly
    identify which search term matched, even when the cell value is longer
    than the search term (prefix matching).
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["Fred"], ["Susan"], ["John"]],
    )
    field = fields[0]
    workspace = table.database.workspace

    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Name List Scan",
        scan_type="list_of_values",
        list_items=["Fred", "Susan", "John"],
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
        whole_words=False,
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error is None or scan.last_error == ""

    results = {r.row_id: r.matched_value for r in scan.results.all()}
    assert results.get(rows[0].id) == "Fred"
    assert results.get(rows[1].id) == "Susan"
    assert results.get(rows[2].id) == "John"


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_list_scan_whole_words_true(enterprise_data_fixture, populate_search_table):
    """
    When ``whole_words=True``, list-of-values scans must only match exact
    tokens, not prefixes.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=True)
    table, fields, rows = enterprise_data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["John"], ["Johnny"], ["Johnson"]],
    )
    field = fields[0]
    workspace = table.database.workspace

    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=user,
        name="Whole Words List",
        scan_type="list_of_values",
        list_items=["John"],
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
        whole_words=True,
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.is_running is False
    assert scan.last_error is None or scan.last_error == ""

    # Only exact match "John" should be found, not "Johnny" or "Johnson".
    matched_row_ids = set(scan.results.values_list("row_id", flat=True))
    assert rows[0].id in matched_row_ids
    assert rows[1].id not in matched_row_ids
    assert rows[2].id not in matched_row_ids

from datetime import timedelta
from io import StringIO

from django.core import serializers
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import override_settings
from django.utils import timezone

import pytest

from baserow.contrib.integrations.mcp.exceptions import MCPServerCredentialUnavailable
from baserow.contrib.integrations.mcp.handler import MCPServerHandler
from baserow.contrib.integrations.mcp.models import MCPServerIntegration
from baserow.core import encryption
from baserow.core.encryption import (
    DecryptionError,
    check_encryption_keys,
    decrypt,
    encrypt,
    get_key_id,
    get_key_ring,
)
from baserow.core.fields import is_unreadable_secret
from baserow.core.integrations.exceptions import IntegrationCredentialRequired
from baserow.core.integrations.service import IntegrationService

KEY_A = "a" * 40
KEY_B = "b" * 40
TOKEN_CONTEXT = "integrations.mcpserverintegration.oauth_access_token"
REFRESH_CONTEXT = "integrations.mcpserverintegration.oauth_refresh_token"


def stored(integration, column="oauth_access_token"):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {column} FROM integrations_mcpserverintegration "  # nosec B608
            "WHERE integration_ptr_id = %s",
            [integration.id],
        )
        return cursor.fetchone()[0]


def write_stored(integration, value, column="oauth_access_token"):
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE integrations_mcpserverintegration SET {column} = %s "  # nosec B608
            "WHERE integration_ptr_id = %s",
            [value, integration.id],
        )


def reload(integration):
    return MCPServerIntegration.objects.get(id=integration.id)


@pytest.mark.django_db
@override_settings(BASEROW_ENCRYPTION_KEY=KEY_A)
def test_secrets_are_stored_encrypted_and_read_back(data_fixture):
    integration = data_fixture.create_mcp_server_integration(
        auth_header_name="Authorization", auth_header_value="Bearer s3cr3t"
    )
    MCPServerIntegration.objects.filter(id=integration.id).update(
        oauth_access_token="access-1"
    )

    raw = stored(integration)
    assert raw.startswith(f"enc:v1:{get_key_ring().primary_id}:")
    assert "access-1" not in raw
    assert "s3cr3t" not in stored(integration, "auth_header_value")
    copy = reload(integration)
    assert copy.oauth_access_token == "access-1"
    assert copy.auth_header_value == "Bearer s3cr3t"


@pytest.mark.django_db
def test_the_same_secret_is_stored_differently_each_time():
    assert encrypt("x", TOKEN_CONTEXT) != encrypt("x", TOKEN_CONTEXT)


@pytest.mark.django_db
def test_empty_secrets_stay_empty(data_fixture):
    integration = data_fixture.create_mcp_server_integration()

    assert stored(integration) == ""
    assert reload(integration).oauth_access_token == ""


@pytest.mark.django_db
def test_a_secret_copied_into_another_column_cant_be_read(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    write_stored(integration, encrypt("access-1", TOKEN_CONTEXT))
    # Someone with write access to the database moves it to another column.
    write_stored(integration, stored(integration), "oauth_refresh_token")

    assert reload(integration).oauth_refresh_token == ""
    with pytest.raises(DecryptionError):
        decrypt(stored(integration, "oauth_refresh_token"), REFRESH_CONTEXT)


@pytest.mark.django_db
def test_plain_text_written_before_encryption_is_still_read(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    write_stored(integration, "legacy-token")

    assert reload(integration).oauth_access_token == "legacy-token"


@pytest.mark.django_db
def test_secrets_can_only_be_filtered_by_whether_they_are_set(data_fixture):
    data_fixture.create_mcp_server_integration()

    with pytest.raises(FieldError):
        list(MCPServerIntegration.objects.filter(oauth_access_token="x"))
    assert MCPServerIntegration.objects.filter(
        oauth_access_token__isnull=False
    ).exists()


@pytest.mark.django_db
def test_a_new_key_reads_old_secrets_through_the_fallbacks(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_A):
        write_stored(integration, encrypt("access-1", TOKEN_CONTEXT))
        old_id = get_key_ring().primary_id

    with override_settings(
        BASEROW_ENCRYPTION_KEY=KEY_B, BASEROW_ENCRYPTION_KEY_FALLBACKS=[KEY_A]
    ):
        assert reload(integration).oauth_access_token == "access-1"
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        assert reload(integration).oauth_access_token == ""
        with pytest.raises(DecryptionError, match=old_id):
            decrypt(stored(integration), TOKEN_CONTEXT)


@pytest.mark.django_db
def test_secrets_written_before_the_key_was_set_stay_readable(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    with override_settings(BASEROW_ENCRYPTION_KEY=""):
        assert get_key_ring().derived_from_secret_key
        write_stored(integration, encrypt("access-1", TOKEN_CONTEXT))

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_A):
        assert reload(integration).oauth_access_token == "access-1"


@pytest.mark.django_db
def test_reencrypting_moves_every_secret_to_the_current_key(data_fixture):
    first = data_fixture.create_mcp_server_integration()
    second = data_fixture.create_mcp_server_integration()
    trashed = data_fixture.create_mcp_server_integration()
    MCPServerIntegration.objects.filter(id=trashed.id).update(trashed=True)
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_A):
        write_stored(first, encrypt("access-1", TOKEN_CONTEXT))
        write_stored(trashed, encrypt("access-3", TOKEN_CONTEXT))
    write_stored(second, "legacy-token")

    with override_settings(
        BASEROW_ENCRYPTION_KEY=KEY_B, BASEROW_ENCRYPTION_KEY_FALLBACKS=[KEY_A]
    ):
        new_id = get_key_ring().primary_id
        out = StringIO()
        call_command("reencrypt_secrets", "--batch-size", "1", stdout=out)
        assert "oauth_access_token: re-encrypted 3" in out.getvalue()

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        for integration in (first, second, trashed):
            assert get_key_id(stored(integration)) == new_id
        assert reload(first).oauth_access_token == "access-1"
        assert reload(second).oauth_access_token == "legacy-token"
        out = StringIO()
        call_command("reencrypt_secrets", "--check", stdout=out)
        assert f"oauth_access_token: {new_id}: 3" in out.getvalue()


@pytest.mark.django_db
def test_reencrypting_reports_secrets_it_cant_read(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_A):
        write_stored(integration, encrypt("access-1", TOKEN_CONTEXT))

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        out, err = StringIO(), StringIO()
        with pytest.raises(CommandError, match="1 secrets"):
            call_command("reencrypt_secrets", stdout=out, stderr=err)

    assert "(missing key): 1" in out.getvalue()
    assert f"{integration.id}:" in err.getvalue()


@override_settings(BASEROW_ENCRYPTION_KEY="too-short")
def test_a_short_key_is_reported_when_django_starts():
    with pytest.raises(ImproperlyConfigured):
        get_key_ring()
    assert [error.id for error in check_encryption_keys(None)] == ["baserow.E002"]


def test_a_tampered_secret_cant_be_read():
    value = encrypt("access-1", TOKEN_CONTEXT)
    tampered = value[:-2] + ("A" if value[-2] != "A" else "B") + value[-1]

    with pytest.raises(DecryptionError):
        decrypt(tampered, TOKEN_CONTEXT)


@pytest.mark.django_db
@override_settings(BASEROW_ENCRYPTION_KEY=KEY_A)
def test_writing_a_ciphertext_stores_it_as_is_and_never_decrypts_it(data_fixture):
    victim = data_fixture.create_mcp_server_integration(
        auth_header_name="Authorization", auth_header_value="Bearer victim"
    )
    attacker = data_fixture.create_mcp_server_integration()
    attacker.auth_header_value = stored(victim, "auth_header_value")
    attacker.save()

    assert reload(attacker).auth_header_value == stored(victim, "auth_header_value")
    assert "Bearer victim" not in str(reload(attacker).auth_header_value)


@pytest.mark.django_db
@override_settings(BASEROW_ENCRYPTION_KEY=KEY_A)
def test_a_secret_that_looks_encrypted_can_be_saved(data_fixture):
    integration = data_fixture.create_mcp_server_integration(
        auth_header_name="X-Key", auth_header_value="enc:v1:deadbeef:abc"
    )

    assert reload(integration).auth_header_value == "enc:v1:deadbeef:abc"


@pytest.mark.django_db
def test_an_unreadable_secret_doesnt_break_loading_the_row(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_A):
        write_stored(integration, encrypt("access-1", TOKEN_CONTEXT))
    raw = stored(integration)

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        copy = reload(integration)
        assert copy.oauth_access_token == ""
        copy.name = "renamed"
        copy.save()
    # Saving the row keeps the stored value, so the old key can still read it.
    assert stored(integration) == raw
    with override_settings(
        BASEROW_ENCRYPTION_KEY=KEY_B, BASEROW_ENCRYPTION_KEY_FALLBACKS=[KEY_A]
    ):
        assert reload(integration).oauth_access_token == "access-1"


@pytest.mark.django_db
def test_an_unreadable_secret_can_be_replaced(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_A):
        write_stored(integration, encrypt("access-1", TOKEN_CONTEXT))

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        copy = reload(integration)
        copy.oauth_access_token = "access-2"
        copy.save()
        assert reload(integration).oauth_access_token == "access-2"


@pytest.mark.django_db
def test_secrets_survive_a_secret_key_change_through_the_fallbacks(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    with override_settings(BASEROW_ENCRYPTION_KEY="", SECRET_KEY="old-short-key"):
        write_stored(integration, encrypt("access-1", TOKEN_CONTEXT))

    with override_settings(
        BASEROW_ENCRYPTION_KEY=KEY_A,
        SECRET_KEY="new-secret-key",
        BASEROW_ENCRYPTION_KEY_FALLBACKS=["old-short-key"],
    ):
        assert reload(integration).oauth_access_token == "access-1"
    with override_settings(
        BASEROW_ENCRYPTION_KEY="",
        SECRET_KEY="new-secret-key",
        SECRET_KEY_FALLBACKS=["old-short-key"],
    ):
        assert reload(integration).oauth_access_token == "access-1"


@pytest.mark.django_db
def test_plain_text_starting_like_a_secret_is_still_read(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    write_stored(integration, "enc:abc")

    assert reload(integration).oauth_access_token == "enc:abc"
    call_command("reencrypt_secrets", stdout=StringIO())
    assert reload(integration).oauth_access_token == "enc:abc"


def header_server(data_fixture, user=None):
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_A):
        return data_fixture.create_mcp_server_integration(
            user=user, auth_header_name="Authorization", auth_header_value="Bearer a"
        )


@pytest.mark.django_db
def test_an_unreadable_secret_still_protects_where_it_is_sent(data_fixture):
    user = data_fixture.create_user()
    integration = header_server(data_fixture, user)

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        copy = reload(integration)
        assert is_unreadable_secret(copy.auth_header_value)
        assert copy.auth_header_value
        with pytest.raises(IntegrationCredentialRequired):
            IntegrationService().update_integration(
                user, copy, url="https://other.example.com/mcp"
            )


@pytest.mark.django_db
def test_switching_the_sign_in_method_clears_an_unreadable_secret(data_fixture):
    user = data_fixture.create_user()
    integration = header_server(data_fixture, user)

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        IntegrationService().update_integration(
            user, reload(integration), auth_type="none"
        )

    assert stored(integration, "auth_header_value") == ""


@pytest.mark.django_db
def test_an_unreadable_secret_is_never_sent(data_fixture):
    integration = header_server(data_fixture)

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        with pytest.raises(MCPServerCredentialUnavailable):
            MCPServerHandler().get_connection(reload(integration))


@pytest.mark.django_db
def test_an_unreadable_refresh_token_is_kept_instead_of_signing_out(data_fixture):
    integration = data_fixture.create_mcp_server_integration(
        auth_type="oauth", oauth_expires_at=timezone.now() + timedelta(seconds=5)
    )
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_A):
        write_stored(
            integration, encrypt("refresh-1", REFRESH_CONTEXT), "oauth_refresh_token"
        )
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        write_stored(integration, encrypt("access-1", TOKEN_CONTEXT))
    refresh_token = stored(integration, "oauth_refresh_token")

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        with pytest.raises(MCPServerCredentialUnavailable):
            MCPServerHandler().get_connection(reload(integration))

    assert stored(integration, "oauth_refresh_token") == refresh_token
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        assert reload(integration).oauth_access_token == "access-1"


@pytest.mark.django_db
@override_settings(BASEROW_ENCRYPTION_KEY=KEY_A)
def test_a_dump_keeps_secrets_encrypted_and_loads_them_back(data_fixture):
    integration = header_server(data_fixture)
    dump = serializers.serialize("json", [integration])

    assert "Bearer a" not in dump
    for obj in serializers.deserialize("json", dump):
        obj.save()

    assert reload(integration).auth_header_value == "Bearer a"


@pytest.mark.django_db
def test_a_dump_keeps_an_unreadable_secret_as_it_is_stored(data_fixture):
    integration = header_server(data_fixture)
    raw = stored(integration, "auth_header_value")

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        dump = serializers.serialize("json", [reload(integration)])
        for obj in serializers.deserialize("json", dump):
            obj.save()

    assert stored(integration, "auth_header_value") == raw


def test_keys_that_share_an_id_are_refused(monkeypatch):
    encryption._build_key_ring.cache_clear()
    monkeypatch.setattr(encryption, "_key_id", lambda key: "e35fbbf5")
    try:
        with override_settings(
            BASEROW_ENCRYPTION_KEY=KEY_B, BASEROW_ENCRYPTION_KEY_FALLBACKS=[KEY_A]
        ):
            with pytest.raises(ImproperlyConfigured, match="e35fbbf5"):
                get_key_ring()
    finally:
        encryption._build_key_ring.cache_clear()


@pytest.mark.django_db
def test_checking_fails_when_a_key_is_missing(data_fixture):
    integration = data_fixture.create_mcp_server_integration()
    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_A):
        write_stored(integration, encrypt("access-1", TOKEN_CONTEXT))

    with override_settings(BASEROW_ENCRYPTION_KEY=KEY_B):
        out = StringIO()
        with pytest.raises(CommandError, match="1 secrets"):
            call_command("reencrypt_secrets", "--check", stdout=out, stderr=StringIO())

    assert "(missing key): 1" in out.getvalue()


@pytest.mark.django_db
@override_settings(BASEROW_ENCRYPTION_KEY=KEY_A)
def test_checking_and_reencrypting_fail_on_a_tampered_current_key_secret(
    data_fixture,
):
    integration = data_fixture.create_mcp_server_integration()
    value = encrypt("access-1", TOKEN_CONTEXT)
    write_stored(
        integration, value[:-2] + ("A" if value[-2] != "A" else "B") + value[-1]
    )

    for args in (["--check"], []):
        out = StringIO()
        with pytest.raises(CommandError, match="1 secrets"):
            call_command("reencrypt_secrets", *args, stdout=out, stderr=StringIO())
        assert "(can't be decrypted): 1" in out.getvalue()


def test_the_batch_size_must_be_positive():
    with pytest.raises(CommandError, match="batch-size"):
        call_command("reencrypt_secrets", "--batch-size", "0")

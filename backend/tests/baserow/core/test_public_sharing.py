from baserow.core.public_sharing import (
    decode_public_access_token,
    encode_public_access_token,
    is_public_access_token_valid,
)


def test_public_access_token_round_trip():
    token = encode_public_access_token("slug", "password-hash")

    assert decode_public_access_token("slug", "password-hash", token) == {
        "slug_id": "slug"
    }
    assert is_public_access_token_valid("slug", "password-hash", token)


def test_public_access_token_is_bound_to_the_slug_and_the_password_hash():
    token = encode_public_access_token("slug", "password-hash")

    assert not is_public_access_token_valid("other-slug", "password-hash", token)
    assert not is_public_access_token_valid("slug", "other-password-hash", token)
    assert not is_public_access_token_valid("slug", "", token)


def test_public_access_token_rejects_garbage():
    assert not is_public_access_token_valid("slug", "password-hash", "not-a-token")
    assert not is_public_access_token_valid("slug", "password-hash", "")

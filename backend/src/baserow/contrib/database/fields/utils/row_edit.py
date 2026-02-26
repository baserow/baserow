from typing import TYPE_CHECKING, Dict, Optional

from django.conf import settings

from itsdangerous import BadSignature, URLSafeSerializer

if TYPE_CHECKING:
    from baserow.contrib.database.views.models import FormView


def _get_row_edit_signer():
    return URLSafeSerializer(settings.SECRET_KEY, salt="form-view-edit-row")


def generate_row_edit_token(row_id: int, view_id: int, field_id: int) -> str:
    """
    Generate a signed, URL-safe token encoding the row, view, and field IDs.

    :param row_id: The primary key of the row.
    :param view_id: The primary key of the form view.
    :param field_id: The primary key of the form_view_edit_row field.
    :return: A URL-safe signed token string.
    """

    return _get_row_edit_signer().dumps(
        {"row_id": row_id, "view_id": view_id, "field_id": field_id}
    )


def build_row_edit_url(row_id: int, form_view: "FormView", field_id: int) -> str:
    """
    Build the full public URL that lets a visitor edit a row via a form view.

    :param row_id: The primary key of the row.
    :param form_view: The form view instance.
    :param field_id: The primary key of the form_view_edit_row field.
    :return: The absolute edit URL.
    """

    token = generate_row_edit_token(row_id, form_view.id, field_id)
    base = getattr(settings, "PUBLIC_WEB_FRONTEND_URL", "").rstrip("/")
    return f"{base}/form/{form_view.slug}/?edit_token={token}"


def verify_and_decode_edit_token(token: str) -> Optional[Dict[str, int]]:
    """
    Decode and verify a row edit token.

    :param token: The signed token string to verify.
    :return: The payload dict containing `row_id`, `view_id`, and `field_id`, or
        `None` if the token is invalid.
    """

    try:
        return _get_row_edit_signer().loads(token)
    except BadSignature:
        return None

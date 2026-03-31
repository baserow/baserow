from typing import TYPE_CHECKING, Dict, Optional

from django.conf import settings

from itsdangerous import BadSignature, URLSafeSerializer

if TYPE_CHECKING:
    from baserow.contrib.database.views.models import FormView


def _get_row_edit_signer():
    return URLSafeSerializer(settings.SECRET_KEY, salt="form-view-edit-row")


def generate_row_edit_token(view_slug: str, field_id: int, cell_uuid: str) -> str:
    """
    Generate a signed, URL-safe token encoding the view slug, field ID, and
    per-cell UUID.

    :param view_slug: The slug of the form view.
    :param field_id: The primary key of the form_view_edit_row field.
    :param cell_uuid: The unique UUID stored in the row's edit-link cell.
    :return: A URL-safe signed token string.
    """

    return _get_row_edit_signer().dumps(
        {"view_slug": view_slug, "field_id": field_id, "cell_uuid": cell_uuid}
    )


def build_row_edit_url(cell_uuid: str, form_view: "FormView", field_id: int) -> str:
    """
    Build the full public URL that lets a visitor edit a row via a form view.

    :param cell_uuid: The unique UUID stored in the row's edit-link cell.
    :param form_view: The form view instance.
    :param field_id: The primary key of the form_view_edit_row field.
    :return: The absolute edit URL.
    """

    token = generate_row_edit_token(form_view.slug, field_id, cell_uuid)
    base = getattr(settings, "PUBLIC_WEB_FRONTEND_URL", "").rstrip("/")
    return f"{base}/form/{form_view.slug}/?edit_token={token}"


def verify_and_decode_edit_token(token: str) -> Optional[Dict[str, str]]:
    """
    Decode and verify a row edit token.

    :param token: The signed token string to verify.
    :return: The payload dict containing `view_slug`, `field_id`, and
        `cell_uuid`, or `None` if the token is invalid.
    """

    try:
        return _get_row_edit_signer().loads(token)
    except BadSignature:
        return None

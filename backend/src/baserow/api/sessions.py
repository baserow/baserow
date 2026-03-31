import re
import uuid
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser

from baserow.api.exceptions import (
    InvalidClientSessionIdAPIException,
    InvalidUndoRedoActionGroupIdAPIException,
)

UNTRUSTED_CLIENT_SESSION_ID_USER_ATTR = "untrusted_client_session_id"
UNDO_REDO_ACTION_GROUP_ID = "untrusted_client_action_group"


def _raise_if_not_valid_untrusted_client_session_id(value: Any):
    is_valid = (
        isinstance(value, str)
        and re.match(r"^[0-9a-zA-Z-]+$", value)
        and len(value) <= settings.MAX_CLIENT_SESSION_ID_LENGTH
    )
    if not is_valid:
        raise InvalidClientSessionIdAPIException()


def set_untrusted_client_session_id_from_request_or_raise_if_invalid(
    user: AbstractUser, request
):
    """
    Extracts the untrusted client session id from the requests headers and sets it
    on a custom attr on the user object for later retrieval. If the header is not set
    then nothing will be set. If the header is set but has an invalid value then an
    APIException will be raised.

    :param user: The user to set the client id attr on.
    :param request: The request containing the headers to check.
    """

    session_id = request.headers.get(settings.CLIENT_SESSION_ID_HEADER, None)
    if session_id is not None:
        _raise_if_not_valid_untrusted_client_session_id(session_id)
        set_untrusted_client_session_id(user, session_id)


def set_untrusted_client_session_id(user: AbstractUser, session_id: str):
    setattr(user, UNTRUSTED_CLIENT_SESSION_ID_USER_ATTR, session_id)


def get_untrusted_client_session_id(user: AbstractUser):
    return getattr(user, UNTRUSTED_CLIENT_SESSION_ID_USER_ATTR, None)


def _raise_if_not_valid_undo_redo_action_group_id(value: Any):
    try:
        uuid.UUID(str(value), version=4)
    except ValueError:
        raise InvalidUndoRedoActionGroupIdAPIException()


def set_client_undo_redo_action_group_id_from_request_or_raise_if_invalid(
    user: AbstractUser, request
):
    """
    Extracts the untrusted client action group from the requests headers and sets it
    on a custom attr on the user object for later retrieval. If the header is not set
    then nothing will be set.
    If the header is set but has an invalid value then an APIException will be raised.

    :param user: The user to set the client id attr on.
    :param request: The request containing the headers to check.
    """

    action_group_id = request.headers.get(
        settings.CLIENT_UNDO_REDO_ACTION_GROUP_ID_HEADER, None
    )
    if action_group_id is not None:
        _raise_if_not_valid_undo_redo_action_group_id(action_group_id)
    set_client_undo_redo_action_group_id(user, action_group_id)


def set_client_undo_redo_action_group_id(user: AbstractUser, action_group_id: str):
    setattr(user, UNDO_REDO_ACTION_GROUP_ID, action_group_id)


def get_client_undo_redo_action_group_id(user: AbstractUser):
    return getattr(user, UNDO_REDO_ACTION_GROUP_ID, None)


def set_user_websocket_id(user, request):
    _set_user_websocket_id(user, request.headers.get(settings.WEBSOCKET_ID_HEADER))


def _set_user_websocket_id(user, websocket_id):
    user.web_socket_id = websocket_id


def get_user_remote_ip_address_from_request(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs: client, proxy1, proxy2.
        # The first one is the original client IP.
        return x_forwarded_for.split(",")[0].strip()

    x_real_ip = request.META.get("HTTP_X_REAL_IP")
    if x_real_ip:
        return x_real_ip.strip()

    return request.META.get("REMOTE_ADDR")


def set_user_remote_addr_ip_from_request(user, request):
    ip_address = get_user_remote_ip_address_from_request(request)
    set_user_remote_addr_ip(user, ip_address)


def set_user_remote_addr_ip(user, ip_address):
    user.remote_addr_ip = ip_address


def get_user_remote_addr_ip(user):
    return getattr(user, "remote_addr_ip", None)


def set_user_session_data_from_request(user, request):
    """
    Sets the user data from the request. This includes the websocket id, the
    session id and the undo/redo action group id.

    :param user: The user for which the data should be set.
    :param request: The request from which the data should be extracted.
    """

    set_user_websocket_id(user, request)
    set_untrusted_client_session_id_from_request_or_raise_if_invalid(user, request)
    set_client_undo_redo_action_group_id_from_request_or_raise_if_invalid(user, request)
    set_user_remote_addr_ip_from_request(user, request)

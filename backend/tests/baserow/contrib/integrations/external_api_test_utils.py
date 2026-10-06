from unittest.mock import Mock


def fake_response(status_code=200, body=None, content=b"{}"):
    """A `requests.Response` stand-in for `send_http_request`."""

    response = Mock()
    response.status_code = status_code
    if body is None:
        response.content = b""
        response.json.side_effect = ValueError("no body")
    else:
        response.content = content
        response.json.return_value = body
    return response

"""
Proof of concept: run Kuma on a ChatGPT plan through Sign in with ChatGPT.

OpenAI's open-source flow only redirects to ``http://127.0.0.1:<port>``, so this
works when the browser and the Baserow backend run on the same machine, such as
a local development stack. Sign in with ``./baserow kuma_chatgpt_login``, then set
``BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=chatgpt:<model slug>``.

The credentials live in one file for the whole instance. A real integration would
store them per Baserow user, because each token spends one person's plan.

See https://developers.openai.com/siwc/token-sharing-open-source
"""

import asyncio
import base64
import dataclasses
import fcntl
import hashlib
import json
import os
import secrets
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import jwt
from openai import AsyncOpenAI
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL = f"{ISSUER}/api/accounts/oauth/token"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
CALLBACK_PATH = "/auth/callback"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
APP_NAME = "Baserow Kuma"
# Refresh this long before the access token expires.
REFRESH_MARGIN_SECONDS = 300

# Responses fields the plan route rejects, by the ModelSettings key that sets them.
# Kuma's model profiles set temperature and max_tokens on every role.
_UNSUPPORTED_SETTINGS = (
    "max_tokens",
    "temperature",
    "top_p",
    "service_tier",
    "openai_service_tier",
    "openai_user",
    "openai_top_logprobs",
    "openai_truncation",
    "openai_background",
    "openai_moderation",
    "openai_prompt_cache_retention",
)
# The plan route only accepts function tools grouped in a namespace.
TOOL_NAMESPACE = "baserow"
TOOL_NAMESPACE_DESCRIPTION = "Tools that read and change the user's Baserow workspace."


class ChatGPTPlanError(Exception):
    """Signing in or refreshing the ChatGPT plan credentials failed."""


def get_credentials_path() -> Path:
    return Path(
        os.getenv("BASEROW_KUMA_CHATGPT_CREDENTIALS_FILE")
        or Path.home() / ".config" / "baserow" / "kuma-chatgpt-plan.json"
    )


def _write_private(path: Path, data: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _read(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


@contextmanager
def _locked(path: Path):
    """Serialize refreshes across processes; refresh tokens rotate on use."""

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _token_request(data: dict) -> dict:
    response = httpx.post(
        TOKEN_URL, data=data, headers={"accept": "application/json"}, timeout=30
    )
    if response.status_code != 200:
        raise ChatGPTPlanError(
            f"Token endpoint returned {response.status_code}: {response.text[:300]} "
            f"(request id {response.headers.get('x-request-id')})"
        )
    return response.json()


def _validate_id_token(id_token: str, client_id: str, nonce: str | None) -> dict:
    key = jwt.PyJWKClient(JWKS_URL).get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        key.key,
        algorithms=["RS256", "ES256"],
        audience=client_id,
        issuer=ISSUER,
    )
    if nonce is not None and claims.get("nonce") != nonce:
        raise ChatGPTPlanError("The ID token nonce does not match this sign-in.")
    return claims


def _store_tokens(path: Path, record: dict, tokens: dict) -> dict:
    record = {
        **record,
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token") or record.get("refresh_token"),
        "expires_at": time.time() + int(tokens.get("expires_in") or 3600),
        "scopes": sorted(
            (tokens.get("scope") or " ".join(record.get("scopes", []))).split()
        ),
    }
    if tokens.get("id_token"):
        record["id_token"] = tokens["id_token"]
    _write_private(path, record)
    return record


def build_authorization(port: int) -> tuple[str, dict]:
    """
    Return the authorization URL and the pending state needed to finish it.

    :param port: The loopback port the callback listener uses.
    """

    path = get_credentials_path()
    record = _read(path)
    host_id = record.get("ext_agent_host_id") or f"urn:uuid:{uuid.uuid4()}"
    if "ext_agent_host_id" not in record:
        _write_private(path, {**record, "ext_agent_host_id": host_id})

    verifier = secrets.token_urlsafe(64)
    pending = {
        "state": secrets.token_urlsafe(32),
        "nonce": secrets.token_urlsafe(32),
        "verifier": verifier,
        "redirect_uri": f"http://127.0.0.1:{port}{CALLBACK_PATH}",
        "client_id": record.get("client_id"),
    }
    params = {
        "response_type": "code",
        "redirect_uri": pending["redirect_uri"],
        "scope": SCOPES,
        "resource": RESOURCE,
        "state": pending["state"],
        "nonce": pending["nonce"],
        "code_challenge_method": "S256",
        "code_challenge": base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        )
        .rstrip(b"=")
        .decode(),
        "ext_agent_host_id": host_id,
    }
    if record.get("client_id"):
        # Reauthorize the existing registration. Access and refresh tokens never go
        # in the URL; the ID token may, as a hint for the authorization endpoint.
        params["client_id"] = record["client_id"]
        if record.get("id_token"):
            params["id_token_hint"] = record["id_token"]
        if record.get("email"):
            params["login_hint"] = record["email"]
    else:
        params["client_id"] = "dynamic_agent_client"
        params["agent_name_hint"] = APP_NAME
    return f"{AUTHORIZE_URL}?{urlencode(params)}", pending


def finish_authorization(callback_url: str, pending: dict) -> dict:
    """
    Exchange the callback's code and save the credentials.

    :param callback_url: The URL OpenAI redirected the browser to.
    :param pending: The state returned by ``build_authorization``.
    :return: The saved credential record.
    """

    query = {k: v[0] for k, v in parse_qs(urlparse(callback_url).query).items()}
    if query.get("state") != pending["state"]:
        raise ChatGPTPlanError("The callback state does not match this sign-in.")
    if "error" in query:
        raise ChatGPTPlanError(f"Authorization failed: {query['error']}")
    client_id = query.get("client_id") or pending["client_id"]
    if not client_id or client_id == "dynamic_agent_client":
        raise ChatGPTPlanError("OpenAI did not return an issued client ID.")
    if pending["client_id"] and client_id != pending["client_id"]:
        raise ChatGPTPlanError("OpenAI returned a different client ID.")

    path = get_credentials_path()
    if not pending["client_id"]:
        # Keep the new registration even if the exchange fails, so the next sign-in
        # reauthorizes it instead of registering another client.
        with _locked(path):
            _write_private(path, {**_read(path), "client_id": client_id})

    tokens = _token_request(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": query["code"],
            "code_verifier": pending["verifier"],
            "redirect_uri": pending["redirect_uri"],
            "resource": RESOURCE,
        }
    )
    claims = _validate_id_token(tokens["id_token"], client_id, pending["nonce"])
    with _locked(path):
        record = {
            **_read(path),
            "client_id": client_id,
            "subject": claims["sub"],
            "email": claims.get("email"),
        }
        return _store_tokens(path, record, tokens)


def get_access_token() -> str:
    """Return a valid access token, refreshing it when it is about to expire."""

    path = get_credentials_path()
    with _locked(path):
        record = _read(path)
        if not record.get("access_token"):
            raise ChatGPTPlanError(
                f"No ChatGPT plan credentials in {path}. "
                "Run `./baserow kuma_chatgpt_login` first."
            )
        if PLAN_SCOPE not in record.get("scopes", []):
            raise ChatGPTPlanError("The ChatGPT plan usage permission was not granted.")
        if record["expires_at"] - REFRESH_MARGIN_SECONDS > time.time():
            return record["access_token"]

        tokens = _token_request(
            {
                "grant_type": "refresh_token",
                "client_id": record["client_id"],
                "refresh_token": record["refresh_token"],
                "resource": RESOURCE,
            }
        )
        if tokens.get("id_token"):
            claims = _validate_id_token(tokens["id_token"], record["client_id"], None)
            if claims["sub"] != record["subject"]:
                raise ChatGPTPlanError("The refreshed token is for another account.")
        return _store_tokens(path, record, tokens)["access_token"]


def _plan_profile(default: ModelProfile) -> ModelProfile:
    """Layer the plan route's request rules on the model's normal OpenAI profile."""

    unsupported = set(default.get("openai_unsupported_model_settings", ()))
    return {
        **default,
        **OpenAIModelProfile(
            openai_unsupported_model_settings=tuple(
                sorted(unsupported | set(_UNSUPPORTED_SETTINGS))
            ),
            # Every request streams, including Agent.run() calls such as the title
            # agent, and nothing is stored. With store=false, pydantic-ai replays
            # reasoning through encrypted content instead of item IDs.
            openai_responses_requires_streaming=True,
            openai_responses_requires_store_false=True,
            # System-role input items are rejected; developer messages are not.
            openai_system_prompt_role="developer",
            openai_supports_input_token_counting=False,
            openai_responses_supports_prompt_cache_diagnostics=False,
        ),
    }


class ChatGPTPlanResponsesModel(OpenAIResponsesModel):
    """
    A Responses model that follows the plan route's request rules. Request fields
    the route rejects are dropped through the profile, and function tools are
    grouped in one namespace.
    """

    def __init__(self, model_name: str, *, provider: OpenAIProvider, **kwargs):
        super().__init__(model_name, provider=provider, profile=_plan_profile, **kwargs)

    async def _build_responses_request_params(self, *args, **kwargs):
        params = await super()._build_responses_request_params(*args, **kwargs)
        if not params.tools:
            return params

        functions = [tool for tool in params.tools if tool.get("type") == "function"]
        if not functions:
            return params
        others = [tool for tool in params.tools if tool.get("type") != "function"]
        namespace = {
            "type": "namespace",
            "name": TOOL_NAMESPACE,
            "description": TOOL_NAMESPACE_DESCRIPTION,
            "tools": functions,
        }
        # The response's function calls carry the namespace, and pydantic-ai sends it
        # back when it replays them.
        return dataclasses.replace(params, tools=[*others, namespace])


async def _async_access_token() -> str:
    # The file lock and token refresh block, so keep them off the event loop.
    return await asyncio.to_thread(get_access_token)


def make_chatgpt_plan_model(name: str) -> Model:
    """Build a Kuma model that spends the signed-in user's ChatGPT plan."""

    # Fail fast with a sign-in hint when there are no usable credentials.
    get_access_token()
    client = AsyncOpenAI(
        # The SDK calls this before each request, so a long Kuma run picks up
        # refreshed tokens.
        api_key=_async_access_token,
        base_url=RESOURCE,
        # RetryingModel retries Kuma's requests; SDK retries would spend the plan
        # twice.
        max_retries=0,
    )
    return ChatGPTPlanResponsesModel(
        name, provider=OpenAIProvider(openai_client=client)
    )

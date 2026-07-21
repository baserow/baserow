import secrets
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin

from django.conf import settings

from itsdangerous import BadSignature, URLSafeTimedSerializer

from baserow.contrib.builder.models import Builder
from baserow.core.cache import global_cache

BUILDER_PREVIEW_COOKIE_BASE_NAME = "baserow_builder_preview"
BUILDER_PREVIEW_TOKEN_QUERY_PARAM = "preview_token"
BUILDER_PREVIEW_GRANT_TOKEN_SALT = "builder-preview-grant"
BUILDER_PREVIEW_SESSION_TOKEN_SALT = "builder-preview-session"
BUILDER_PREVIEW_GRANT_CACHE_KEY = "builder_preview_grant_{grant_id}"


def get_builder_preview_cookie_name() -> str:
    return f"{settings.FRONTEND_COOKIE_PREFIX}{BUILDER_PREVIEW_COOKIE_BASE_NAME}"


class BuilderPreviewGrantDoesNotExist(Exception):
    pass


class BuilderPreviewGrantInvalid(Exception):
    pass


@dataclass(frozen=True)
class BuilderPreviewActor:
    builder_id: int
    workspace_id: int | None
    grant_id: int
    issued_by_user_id: int

    is_authenticated = True
    is_anonymous = False
    is_builder_preview_actor = True

    @property
    def id(self):
        return self.grant_id

    @property
    def pk(self):
        return self.grant_id


class BuilderPreviewGrantHandler:
    def create_grant(self, builder: Builder, issued_by_user) -> str:
        payload = {
            "builder_id": builder.id,
            "workspace_id": builder.workspace_id,
            "issued_by_user_id": issued_by_user.id,
            "preview_actor_id": secrets.randbits(63),
        }
        return self.get_grant_signer().dumps(payload)

    def get_preview_url(self, builder_id: int, path: str, token: str) -> str:
        base_url = settings.BUILDER_PREVIEW_URL.rstrip("/")
        path = path if path.startswith("/") else f"/{path}"
        preview_path = f"{settings.BUILDER_PREVIEW_PATH_PREFIX}{path}"
        url = urljoin(base_url, preview_path)
        separator = "&" if "?" in url else "?"
        return (
            f"{url}{separator}{urlencode({BUILDER_PREVIEW_TOKEN_QUERY_PARAM: token})}"
        )

    def exchange_token(self, token: str) -> tuple[BuilderPreviewActor, str]:
        actor = self._actor_from_token(token, self.get_grant_signer())
        self._consume_grant(actor.grant_id)
        session_token = self.get_session_signer().dumps(self._actor_to_payload(actor))
        return actor, session_token

    def actor_from_token(self, token: str) -> BuilderPreviewActor:
        return self._actor_from_token(token, self.get_session_signer())

    def _actor_from_token(
        self, token: str, signer: URLSafeTimedSerializer
    ) -> BuilderPreviewActor:
        try:
            payload = signer.loads(
                token,
                max_age=self.get_token_ttl_seconds(),
            )
        except BadSignature as exc:
            raise BuilderPreviewGrantInvalid from exc

        if not isinstance(payload, dict):
            raise BuilderPreviewGrantInvalid
        try:
            builder_id = int(payload["builder_id"])
            workspace_id = payload["workspace_id"]
            issued_by_user_id = int(payload["issued_by_user_id"])
            preview_actor_id = int(payload["preview_actor_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BuilderPreviewGrantInvalid from exc

        return BuilderPreviewActor(
            builder_id=builder_id,
            workspace_id=int(workspace_id) if workspace_id is not None else None,
            grant_id=preview_actor_id,
            issued_by_user_id=issued_by_user_id,
        )

    def _consume_grant(self, grant_id: int) -> None:
        exchange_id = secrets.token_urlsafe(32)
        cached_exchange_id = global_cache.get(
            self.get_grant_cache_key(grant_id),
            default=exchange_id,
            timeout=self.get_token_ttl_seconds(),
        )
        if cached_exchange_id != exchange_id:
            raise BuilderPreviewGrantInvalid

    @staticmethod
    def _actor_to_payload(actor: BuilderPreviewActor) -> dict:
        return {
            "builder_id": actor.builder_id,
            "workspace_id": actor.workspace_id,
            "issued_by_user_id": actor.issued_by_user_id,
            "preview_actor_id": actor.grant_id,
        }

    @staticmethod
    def get_grant_cache_key(grant_id: int) -> str:
        return BUILDER_PREVIEW_GRANT_CACHE_KEY.format(grant_id=grant_id)

    @staticmethod
    def get_token_ttl_seconds() -> int:
        return int(settings.BUILDER_PREVIEW_GRANT_TTL.total_seconds())

    @staticmethod
    def get_grant_signer() -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(
            settings.SECRET_KEY, BUILDER_PREVIEW_GRANT_TOKEN_SALT
        )

    @staticmethod
    def get_session_signer() -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(
            settings.SECRET_KEY, BUILDER_PREVIEW_SESSION_TOKEN_SALT
        )

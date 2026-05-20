from dataclasses import dataclass
from typing import Optional, Type, TypedDict

from baserow.core.auth_provider.models import BaseAuthProviderModel

AuthProviderModelSubClass = Type[BaseAuthProviderModel]


class AuthProviderTypeDict(TypedDict):
    id: int
    type: str
    domain: str
    enabled: bool
    allow_existing_users: bool


@dataclass
class UserInfo:
    email: str
    name: str
    language: Optional[str] = None
    workspace_invitation_token: Optional[str] = None

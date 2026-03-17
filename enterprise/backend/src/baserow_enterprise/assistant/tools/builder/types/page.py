"""
Builder page type models.

Defines ``PageCreate`` for creating pages and ``PageItem`` for reading them back.
"""

from typing import Literal

from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel

RoleType = Literal["allow_all", "allow_all_except", "disallow_all_except"]


class PagePathParam(BaseModel):
    """A path parameter definition (e.g. ``id`` in ``/products/:id``)."""

    name: str = Field(..., description="Parameter name.")
    type: Literal["text", "numeric"] = Field("text", description="Parameter type.")


class PageQueryParam(BaseModel):
    """A query parameter definition."""

    name: str = Field(..., description="Parameter name.")
    type: Literal["text", "numeric"] = Field("text", description="Parameter type.")


class PageCreate(BaseModel):
    """Page creation payload."""

    name: str = Field(..., description="Page name (unique in app).")
    path: str = Field(..., description="URL path, e.g. '/products/:id'.")
    path_params: list[PagePathParam] = Field(
        default_factory=list, description="Path parameters."
    )
    query_params: list[PageQueryParam] = Field(
        default_factory=list, description="Query parameters."
    )
    visibility: Literal["all", "logged-in"] = Field(
        "all", description="'all' or 'logged-in'."
    )
    role_type: RoleType = Field(
        "allow_all",
        description=(
            "Role access strategy. Only relevant when visibility='logged-in'. "
            "Use list_pages to see available_roles."
        ),
    )
    roles: list[str] = Field(
        default_factory=list,
        description="Role names for the access strategy.",
    )


class PageUpdate(BaseModel):
    """
    Update an existing page's properties.

    All fields are optional. Only non-None fields are sent to the service layer.
    """

    page_id: int = Field(..., description="ID of the page to update.")
    name: str | None = Field(default=None, description="New page name.")
    path: str | None = Field(default=None, description="New URL path.")
    path_params: list[PagePathParam] | None = Field(
        default=None, description="New path parameters."
    )
    query_params: list[PageQueryParam] | None = Field(
        default=None, description="New query parameters."
    )
    visibility: Literal["all", "logged-in"] | None = Field(
        default=None, description="Page visibility."
    )
    role_type: RoleType | None = Field(
        default=None, description="Role access strategy."
    )
    roles: list[str] | None = Field(
        default=None, description="Role names for the access strategy."
    )

    def to_update_kwargs(self) -> dict:
        """Return kwargs for ``PageService.update_page()``."""

        kwargs: dict = {}
        if self.name is not None:
            kwargs["name"] = self.name
        if self.path is not None:
            kwargs["path"] = self.path
        if self.path_params is not None:
            kwargs["path_params"] = [p.model_dump() for p in self.path_params]
        if self.query_params is not None:
            kwargs["query_params"] = [q.model_dump() for q in self.query_params]
        if self.visibility is not None:
            kwargs["visibility"] = self.visibility
        if self.role_type is not None:
            kwargs["role_type"] = self.role_type
        if self.roles is not None:
            kwargs["roles"] = self.roles
        return kwargs

    def get_updated_field_names(self) -> list[str]:
        """Return names of fields that were explicitly set (non-None)."""

        skip = {"page_id"}
        return [
            name
            for name in self.__class__.model_fields
            if name not in skip and getattr(self, name) is not None
        ]


class PageItem(BaseModel):
    """Existing page with ID."""

    id: int
    name: str
    path: str
    path_params: list[PagePathParam] = Field(default_factory=list)
    query_params: list[PageQueryParam] = Field(default_factory=list)
    visibility: str = "all"
    role_type: str = "allow_all"
    roles: list[str] = Field(default_factory=list)

    @classmethod
    def from_orm(cls, page) -> "PageItem":
        """Create a PageItem from a Django Page instance."""

        path_params = []
        for p in page.path_params or []:
            if isinstance(p, dict):
                path_params.append(
                    PagePathParam(name=p["name"], type=p.get("type", "text"))
                )

        query_params = []
        for q in page.query_params or []:
            if isinstance(q, dict):
                query_params.append(
                    PageQueryParam(name=q["name"], type=q.get("type", "text"))
                )

        return cls(
            id=page.id,
            name=page.name,
            path=page.path,
            path_params=path_params,
            query_params=query_params,
            visibility=page.visibility,
            role_type=page.role_type,
            roles=page.roles or [],
        )

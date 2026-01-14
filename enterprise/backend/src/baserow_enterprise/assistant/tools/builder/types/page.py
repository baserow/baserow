from typing import Literal

from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel


class PagePathParam(BaseModel):
    """Path parameter definition for a page."""

    name: str = Field(..., description="Parameter name matching :name in path")
    type: Literal["text", "numeric"] = Field(
        default="text", description="Parameter type for validation"
    )


class PageQueryParam(BaseModel):
    """Query parameter definition for a page."""

    name: str = Field(..., description="Query parameter name")
    type: Literal["text", "numeric"] = Field(
        default="text", description="Parameter type for validation"
    )


class PageCreate(BaseModel):
    """Create a new page in an application builder."""

    name: str = Field(..., description="Display name of the page")
    path: str = Field(
        ...,
        description="URL path. Use :param for path parameters (e.g., '/products/:id')",
    )
    path_params: list[PagePathParam] = Field(
        default_factory=list,
        description="Path parameters - must match :param placeholders in path",
    )
    query_params: list[PageQueryParam] = Field(
        default_factory=list, description="Query parameters available on this page"
    )
    visibility: Literal["all", "logged-in"] = Field(
        default="all",
        description="Page visibility: 'all' for public, 'logged-in' for authenticated users",
    )

    def to_orm_kwargs(self) -> dict:
        """Convert to kwargs for PageHandler.create_page()."""

        return {
            "name": self.name,
            "path": self.path,
            "path_params": [p.model_dump() for p in self.path_params],
            "query_params": [p.model_dump() for p in self.query_params],
        }


class PageItem(PageCreate):
    """Existing page with ID."""

    id: int = Field(..., description="Page ID")

    @classmethod
    def from_orm(cls, page) -> "PageItem":
        """Create PageItem from ORM Page instance."""

        return cls(
            id=page.id,
            name=page.name,
            path=page.path,
            path_params=[
                PagePathParam(name=p["name"], type=p.get("type", "text"))
                for p in (page.path_params or [])
            ],
            query_params=[
                PageQueryParam(name=p["name"], type=p.get("type", "text"))
                for p in (page.query_params or [])
            ],
            visibility="logged-in" if page.visibility == "logged-in" else "all",
        )

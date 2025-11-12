from typing import List, Optional, TypedDict

from baserow.contrib.builder.pages.types import PagePathParams, PageQueryParams
from baserow.core.formula import BaserowFormulaObject
from baserow.core.integrations.types import IntegrationDictSubClass
from baserow.core.services.types import ServiceDictSubClass
from baserow.core.user_sources.types import UserSourceDictSubClass
from baserow.core.workflow_actions.models import WorkflowAction


class ElementDict(TypedDict):
    id: int
    order: int
    type: str
    parent_element_id: int
    place_in_container: str
    css_classes: str
    visibility: str
    visibility_condition: BaserowFormulaObject
    role_type: str
    roles: list
    styles: dict
    style_border_top_color: str
    style_border_top_size: int
    style_padding_top: int
    style_margin_top: int
    style_border_bottom_color: str
    style_border_bottom_size: int
    style_padding_bottom: int
    style_margin_bottom: int
    style_border_left_color: str
    style_border_left_size: int
    style_padding_left: int
    style_margin_left: int
    style_border_right_color: str
    style_border_right_size: int
    style_padding_right: int
    style_margin_right: int
    style_background_radius: int
    style_border_radius: int
    style_background: str
    style_background_color: str
    style_background_file_id: str
    style_background_mode: str
    style_width: str
    style_width_child: str


class DataSourceDict(TypedDict):
    id: int
    name: str
    order: int
    service: Optional[ServiceDictSubClass]


class PageDict(TypedDict):
    id: int
    name: str
    order: int
    path: str
    path_params: PagePathParams
    query_params: PageQueryParams
    elements: List[ElementDict]
    data_sources: List[DataSourceDict]
    workflow_actions: List[WorkflowAction]
    visibility: Optional[str]
    role_type: Optional[str]
    roles: Optional[List[str]]


class BuilderDict(TypedDict):
    id: int
    name: str
    order: int
    type: str
    pages: List[PageDict]
    integrations: List[IntegrationDictSubClass]
    user_sources: List[UserSourceDictSubClass]
    theme: object
    favicon_file: Optional[dict]
    login_page: Optional[PageDict]

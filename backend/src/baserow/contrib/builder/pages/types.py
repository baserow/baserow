from typing import List, Literal, TypedDict

PAGE_PATH_PARAM_TYPE_CHOICES_LITERAL = Literal["text", "numeric"]


class PagePathParam(TypedDict):
    name: str
    param_type: Literal[PAGE_PATH_PARAM_TYPE_CHOICES_LITERAL]

PagePathParams = List[PagePathParam]

class PageQueryParam(TypedDict):
    name: str
    param_type: Literal[PAGE_PATH_PARAM_TYPE_CHOICES_LITERAL]


PageQueryParams = List[PageQueryParam]

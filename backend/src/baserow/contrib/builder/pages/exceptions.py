from typing import List

from baserow.contrib.builder.pages.constants import PAGE_PARAM_TYPE_CHOICES


class PageDoesNotExist(Exception):
    """Raised when trying to get a page that doesn't exist."""


class PageNotInBuilder(Exception):
    """Raised when trying to get a page that does not belong to the correct builder"""

    def __init__(self, page_id=None, *args, **kwargs):
        self.page_id = page_id
        super().__init__(
            f"The page {page_id} does not belong to the builder.",
            *args,
            **kwargs,
        )


class SharedPageIsReadOnly(Exception):
    """Raised when trying to do something on shared page."""


class PageNameNotUnique(Exception):
    """Raised when a page is trying to be created with a name that already exists"""

    def __init__(self, name=None, builder_id=None, *args, **kwargs):
        self.name = name
        self.builder_id = builder_id
        super().__init__(
            f"A page with the name {name} already exists in the builder with id "
            f"{builder_id}",
            *args,
            **kwargs,
        )


class PagePathNotUnique(Exception):
    """Raised when a page is trying to be created with a path that already exists"""

    def __init__(self, path=None, builder_id=None, *args, **kwargs):
        self.path = path
        self.builder_id = builder_id
        super().__init__(
            f"A page with the path {path} already exists in the builder with id "
            f"{builder_id}",
            *args,
            **kwargs,
        )


class PathParamNotInPath(Exception):
    """Raised when a path param is not in the path itself"""

    def __init__(self, path: str, path_param_name: str, *args, **kwargs):
        self.path = path
        self.path_param_name = path_param_name
        super().__init__(
            f"The path param {path_param_name} doesn't exist in path {path}"
        )


class PathParamNotDefined(Exception):
    """Raised when a path param is in a path but not defined as a path param"""

    def __init__(
        self,
        path: str,
        path_param_name: str,
        path_param_names: List[str],
        *args,
        **kwargs,
    ):
        self.path = path
        self.path_param_name = path_param_name
        self.path_param_names = path_param_names
        super().__init__(
            f"The path param {path_param_name} in path {path} has not been defined in "
            f"the given path params of {path_param_names}"
        )


class InvalidPagePathParamType(Exception):
    """Raised when an invalid page path param type is being set"""

    def __init__(self, param_type: str, *args, **kwargs):
        self.param_type = param_type
        super().__init__(
            f"The param type {param_type} is invalid, please chose from "
            f"{PAGE_PARAM_TYPE_CHOICES}"
        )


class DuplicatePathParamsInPath(Exception):
    """Raised when a path param is defined multiple times in a path"""

    def __init__(self, path: str, path_param_names: List[str], *args, **kwargs):
        self.path = path
        self.path_param_names = path_param_names
        super().__init__(
            f"The path params {path_param_names} are defined multiple times "
            f"in path {path}"
        )


class InvalidQueryParamName(Exception):
    """Raised when an invalid query param name is being set"""

    def __init__(self, query_param_name: str, *args, **kwargs):
        self.query_param_name = query_param_name
        super().__init__(f"The query param {query_param_name} is invalid")


class DuplicatePageParams(Exception):
    """Raised when same query param is defined multiple times or query
    param names clash with path param names."""

    def __init__(
        self,
        param: str,
        query_param_names: List[str],
        path_param_names: List[str],
        *args,
        **kwargs,
    ):
        self.query_param_names = query_param_names
        self.path_param_names = path_param_names
        self.param = param
        super().__init__(
            f"The query param {param} is defined multiple times in {query_param_names}"
            f"or clash with path params {path_param_names}"
        )

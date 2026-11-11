"""
Page parameter order. The types and the helpers both use it, so it imports neither.
"""

from collections.abc import Callable
from operator import attrgetter
from typing import TypeVar

from baserow.contrib.builder.pages.models import Page

T = TypeVar("T")


def parameters_in_page_order(
    builder_id: int,
    page_id: int | None,
    parameters: list[T] | None,
    name_of: Callable[[T], str] = attrgetter("name"),
) -> list[T] | None:
    """
    Sort page parameters like the path parameters of the page they open, because the
    frontend hides a link or button whose names are in another order.

    :param builder_id: The application the page must be in.
    :param page_id: The page they open.
    :param parameters: The parameters.
    :param name_of: Reads a parameter's name.
    :return: The sorted parameters, the ones the page doesn't have last. They come
        back as given when there's no such page in the application.
    """

    if not parameters:
        return parameters
    page = Page.objects.filter(id=page_id, builder_id=builder_id).first()
    if page is None:
        return parameters
    order = {param["name"]: i for i, param in enumerate(page.path_params or [])}
    return sorted(parameters, key=lambda param: order.get(name_of(param), len(order)))

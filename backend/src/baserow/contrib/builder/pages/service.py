from typing import List, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.operations import OrderPagesBuilderOperationType
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.operations import (
    CreatePageOperationType,
    DeletePageOperationType,
    DuplicatePageOperationType,
    ReadPageOperationType,
    UpdatePageOperationType,
)
from baserow.contrib.builder.pages.signals import (
    page_created,
    page_deleted,
    page_updated,
    pages_reordered,
)
from baserow.contrib.builder.pages.types import PagePathParams, PageQueryParams
from baserow.core.handler import CoreHandler
from baserow.core.utils import ChildProgressBuilder, extract_allowed


class PageService:
    def __init__(self):
        self.handler = PageHandler()

    def get_page(self, user: AbstractUser, page_id: int) -> Page:
        """
        Gets a page by ID

        :param user: The user requesting the page
        :param page_id: The ID of the page
        :return: The model instance of the Page
        """

        page = self.handler.get_page(page_id)

        CoreHandler().check_permissions(
            user,
            ReadPageOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        return page

    def create_page(
        self,
        user: AbstractUser,
        builder: Builder,
        name: str,
        path: str,
        path_params: PagePathParams = None,
        query_params: PageQueryParams = None,
    ) -> Page:
        """
        Creates a new page

        :param user: The user trying to create the page
        :param builder: The builder the page belongs to
        :param name: The name of the page
        :param path: The path of the page
        :param path_params: The params of the path provided
        :return: The newly created page instance
        """

        CoreHandler().check_permissions(
            user,
            CreatePageOperationType.type,
            workspace=builder.workspace,
            context=builder,
        )

        page = self.handler.create_page(
            builder, name, path, path_params=path_params, query_params=query_params
        )

        page_created.send(self, page=page, user=user)

        return page

    def delete_page(self, user: AbstractUser, page: Page):
        """
        Deletes the page provided

        :param user: The user trying to delete the page
        :param page: The page that must be deleted
        """

        CoreHandler().check_permissions(
            user,
            DeletePageOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        page_id = page.id

        self.handler.delete_page(page)

        page_deleted.send(self, builder=page.builder, page_id=page_id, user=user)

    def update_page(self, user: AbstractUser, page: Page, **kwargs) -> Page:
        """
        Updates fields of a page

        :param user: The user trying to update the page
        :param page: The page that should be updated
        :param kwargs: The fields that should be updated with their corresponding value
        :return: The updated page
        """

        CoreHandler().check_permissions(
            user,
            UpdatePageOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        allowed_updates = extract_allowed(
            kwargs,
            [
                "name",
                "path",
                "path_params",
                "visibility",
                "role_type",
                "roles",
                "query_params",
            ],
        )

        self.handler.update_page(page, **allowed_updates)

        page_updated.send(self, page=page, user=user)

        return page

    def order_pages(
        self, user: AbstractUser, builder: Builder, order: List[int]
    ) -> List[int]:
        """
        Assigns a new order to the pages in a builder application.

        :param user: The user trying to order the pages
        :param builder: The builder that the pages belong to
        :param order: The new order of the pages
        :return: The new order of the pages
        """

        CoreHandler().check_permissions(
            user,
            OrderPagesBuilderOperationType.type,
            workspace=builder.workspace,
            context=builder,
        )

        all_pages = self.handler.get_pages(
            builder, base_queryset=Page.objects_without_shared
        )

        user_pages = CoreHandler().filter_queryset(
            user,
            OrderPagesBuilderOperationType.type,
            all_pages,
            workspace=builder.workspace,
        )

        full_order = self.handler.order_pages(builder, order, user_pages)

        pages_reordered.send(self, builder=builder, order=full_order, user=user)

        return full_order

    def duplicate_page(
        self,
        user: AbstractUser,
        page: Page,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Page:
        """
        Duplicates an existing page instance

        :param user: The user initiating the page duplication
        :param page: The page that is being duplicated
        :param progress_builder: A progress object that can be used to report progress
        :raises ValueError: When the provided page is not an instance of Page.
        :return: The duplicated page
        """

        CoreHandler().check_permissions(
            user, DuplicatePageOperationType.type, page.builder.workspace, context=page
        )

        page_clone = PageHandler().duplicate_page(page, progress_builder)

        page_created.send(self, page=page_clone, user=user)

        return page_clone

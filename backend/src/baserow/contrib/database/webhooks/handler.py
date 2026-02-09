import json
import uuid
from typing import TYPE_CHECKING, List, Optional

from django.conf import settings
from django.contrib.auth.models import User as DjangoUser
from django.db.models import Q
from django.db.models.query import QuerySet

from requests import PreparedRequest, Response

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.models import View
from baserow.core.handler import CoreHandler
from baserow.core.utils import extract_allowed, set_allowed_attrs

from .exceptions import (
    TableWebhookDoesNotExist,
    TableWebhookEventConfigFieldNotInTable,
    TableWebhookEventConfigViewNotInTable,
    TableWebhookMaxAllowedCountExceeded,
)
from .models import (
    TableWebhook,
    TableWebhookCall,
    TableWebhookEvent,
    TableWebhookHeader,
)
from .operations import (
    CreateWebhookOperationType,
    DeleteWebhookOperationType,
    ListTableWebhooksOperationType,
    ReadWebhookOperationType,
    TestTriggerWebhookOperationType,
    UpdateWebhookOperationType,
)
from .registries import webhook_event_type_registry
from .typing import EventConfigItem
from .validators import get_webhook_request_function

if TYPE_CHECKING:
    from baserow.contrib.database.webhooks.registries import WebhookEventType


class WebhookHandler:
    def find_webhooks_to_call(
        self, webhook_event_type: "WebhookEventType", **webhook_event_type_kwargs
    ) -> QuerySet[TableWebhook]:
        """
        This function is responsible for finding all the webhooks related to the given
        webhook_event_type that must be triggered on a specific event, defined by the
        webhook_event_type_kwargs. It will return a queryset of webhooks that must be
        triggered.

        :param webhook_event_type: The event type that must be triggered.
        :param webhook_event_type_kwargs: Additional arguments that can be used to
            filter the webhooks.
        :return: The webhooks that must be triggered.
        """

        q = webhook_event_type.get_filters_for_webhooks_to_call(
            **webhook_event_type_kwargs
        )

        return (
            TableWebhook.objects.filter(q)
            .prefetch_related("headers", "events__fields", "events__views")
            .select_related("table__database")
        )

    def get_table_webhook(
        self,
        user: DjangoUser,
        webhook_id: int,
        base_queryset: Optional[QuerySet] = None,
    ) -> TableWebhook:
        """
        Verifies that the calling user has access to the specified table and if so
        returns the webhook if it exists.

        :param user: The user on whose behalf the webhook is requested.
        :param base_queryset: Can be provided if an alternative base queryset could
            be used. This can useful when doing a select for update for example.
        :param webhook_id: The webhook that must be fetched.
        :return: The webhook object related to the provided id.
        """

        webhook = self._get_table_webhook(webhook_id, base_queryset=base_queryset)

        workspace = webhook.table.database.workspace
        CoreHandler().check_permissions(
            user,
            ReadWebhookOperationType.type,
            workspace=workspace,
            context=webhook.table,
        )

        return webhook

    def _get_table_webhook(
        self, webhook_id: int, base_queryset: Optional[QuerySet] = None
    ) -> TableWebhook:
        """
        Fetches a single webhook related to the provided id.

        :param webhook_id: The webhook that must be fetched.
        :param base_queryset: Can be provided if an alternative base queryset could
            be used. This can useful when doing a select for update for example.
        :raises TableWebhookDoesNotExist: When the web hook does not exist.
        :return: The webhook object related to the provided id.
        """

        if base_queryset is None:
            base_queryset = TableWebhook.objects

        try:
            webhook = (
                base_queryset.select_related("table__database__workspace")
                .prefetch_related("events", "events__fields")
                .get(id=webhook_id)
            )
        except TableWebhook.DoesNotExist:
            raise TableWebhookDoesNotExist(
                f"The webhook with id {webhook_id} does not exist."
            )

        return webhook

    def get_all_table_webhooks(self, user: any, table: Table) -> QuerySet:
        """
        Gets all the webhooks for a specific table.

        :param user: The user on whose behalf the tables are requested.
        :param table: The table for which the webhooks must be fetched.
        :return: The fetched webhooks related to the table.
        """

        workspace = table.database.workspace
        CoreHandler().check_permissions(
            user,
            ListTableWebhooksOperationType.type,
            workspace=workspace,
            context=table,
        )

        return TableWebhook.objects.prefetch_related(
            "events", "headers", "calls"
        ).filter(table_id=table.id)

    def _update_webhook_event_config(
        self,
        webhook: TableWebhook,
        event_config: List[EventConfigItem],
        webhook_events: Optional[List[TableWebhookEvent]] = None,
    ):
        """
        Updates the event config of the given by setting the field relationships of the
        events.

        :param webhook: The webhook for which the event config must be updated.
        :param event_config: The event config can contain a list of objects that is used
            to update details about an event.
        :param webhook_events: If the existing webhook events have already been
            fetched, they can be provided here.
        """

        if webhook_events is None:
            webhook_events = TableWebhookEvent.objects.filter(webhook_id=webhook.id)

        for event in event_config:
            event_object = next(
                (o for o in webhook_events if o.event_type == event["event_type"]),
                None,
            )
            # Don't do anything if the related event type doesn't exist because it
            # could have been deleted.
            if not event_object:
                continue

            # Set fields
            field_ids = event.get("fields", [])
            fields = Field.objects.filter(table_id=webhook.table_id, id__in=field_ids)
            for field_id in field_ids:
                if not next((f for f in fields if field_id == f.id), None):
                    raise TableWebhookEventConfigFieldNotInTable(field_id)

            event_object.fields.set(fields)

            # Set views
            view_ids = event.get("views", [])
            views = View.objects.filter(id__in=view_ids, table_id=webhook.table_id)
            for view_id in view_ids:
                if not next((v for v in views if view_id == v.id), None):
                    raise TableWebhookEventConfigViewNotInTable(view_id)

            event_object.views.set(views)
            event_object.get_type().after_update(event_object)

    def create_table_webhook(
        self,
        user: DjangoUser,
        table: Table,
        events: Optional[List[str]] = None,
        event_config: Optional[List[EventConfigItem]] = None,
        headers: Optional[dict] = None,
        **kwargs: dict,
    ) -> TableWebhook:
        """
        Creates a new webhook for a given table.

        :param user: The user on whose behalf the webhook is created.
        :param table: The table for which the webhook must be created.
        :param events: A list containing the event types related to the webhook. They
            will only be added if the provided `include_all_events` is False.
        :param event_config: The event config object used for the update. This can be
            used to select the related fields, for example.
        :param headers: An object containing the additional headers that must be sent
            when the webhook triggers. The key is the name and the value.
        :param kwargs: Additional arguments passed along to the webhook object.
        :return: The newly created webhook object.
        """

        workspace = table.database.workspace
        CoreHandler().check_permissions(
            user, CreateWebhookOperationType.type, workspace=workspace, context=table
        )

        webhook_count = TableWebhook.objects.filter(table_id=table.id).count()

        if webhook_count >= settings.BASEROW_WEBHOOKS_MAX_PER_TABLE:
            raise TableWebhookMaxAllowedCountExceeded

        allowed_fields = [
            "use_user_field_names",
            "url",
            "request_method",
            "name",
            "include_all_events",
        ]
        values = extract_allowed(kwargs, allowed_fields)
        webhook = TableWebhook.objects.create(table_id=table.id, **values)

        webhook_events = []
        if events is not None and not values.get("include_all_events"):
            for event_type in events:
                webhook_event = TableWebhookEvent(
                    event_type=event_type, webhook=webhook
                )
                webhook_event.full_clean()
                webhook_events.append(webhook_event)

            webhook_events = TableWebhookEvent.objects.bulk_create(webhook_events)

        if event_config is not None and not values.get("include_all_events"):
            self._update_webhook_event_config(webhook, event_config, webhook_events)

        if headers is not None:
            header_objects = []
            for key, value in headers.items():
                header = TableWebhookHeader(
                    name=key, value=value, webhook_id=webhook.id
                )
                header.full_clean()
                header_objects.append(header)

            TableWebhookHeader.objects.bulk_create(header_objects)
        return webhook

    def update_table_webhook(
        self,
        user: DjangoUser,
        webhook: TableWebhook,
        events: Optional[List[str]] = None,
        event_config: Optional[List[EventConfigItem]] = None,
        headers: Optional[List[dict]] = None,
        **kwargs: dict,
    ) -> TableWebhook:
        """
        Updates a specific table webhook.

        :param user: The user on whose behalf the webhook is updated.
        :param webhook: The webhook object that must be updated.
        :param events: A list containing the event types related to the webhook. They
            will only be added if the provided `include_all_events` is False.
        :param event_config: The event config object used for the update. This can be
            used to select the related fields, for example.
        :param headers: An object containing the additional headers that must be sent
            when the webhook triggers. The key is the name and the value the value.
        :param kwargs: Additional arguments passed along to the webhook object.
        :return: The updated webhook object.
        """

        workspace = webhook.table.database.workspace
        CoreHandler().check_permissions(
            user,
            UpdateWebhookOperationType.type,
            workspace=workspace,
            context=webhook.table,
        )

        # if the webhook is not active and a user sets the webhook to active
        # we want to make sure to reset the failed_triggers counter
        if not webhook.active and kwargs.get("active", False):
            webhook.failed_triggers = 0

        old_include_all_events = webhook.include_all_events
        allowed_fields = [
            "use_user_field_names",
            "url",
            "request_method",
            "name",
            "include_all_events",
            "active",
        ]
        webhook = set_allowed_attrs(kwargs, allowed_fields, webhook)
        webhook.save()

        should_update_events = not (
            kwargs.get("include_all_events", False) and not old_include_all_events
        )

        if not should_update_events:
            TableWebhookEvent.objects.filter(webhook=webhook).delete()
        elif events is not None:
            existing_events = webhook.events.all()

            event_ids_to_delete = [
                existing.id
                for existing in existing_events
                if existing.event_type not in events
            ]

            if len(event_ids_to_delete) > 0:
                TableWebhookEvent.objects.filter(
                    webhook=webhook, id__in=event_ids_to_delete
                ).delete()

            existing_event_types = [event.event_type for event in existing_events]
            events_to_create = [
                TableWebhookEvent(webhook=webhook, event_type=event_type)
                for event_type in events
                if event_type not in existing_event_types
            ]

            if len(events_to_create) > 0:
                TableWebhookEvent.objects.bulk_create(events_to_create)

        if event_config is not None and should_update_events:
            self._update_webhook_event_config(webhook, event_config)

        if headers is not None:
            existing_headers = webhook.headers.all()

            header_ids_to_delete = [
                existing.id
                for existing in existing_headers
                if existing.name not in headers
            ]
            if len(header_ids_to_delete) > 0:
                TableWebhookHeader.objects.filter(
                    webhook=webhook, id__in=header_ids_to_delete
                ).delete()

            headers_to_create = []
            for name, value in headers.items():
                try:
                    header = next(
                        existing_header
                        for existing_header in existing_headers
                        if existing_header.name == name
                    )
                    header.value = value
                    header.save()
                except StopIteration:
                    headers_to_create.append(
                        TableWebhookHeader(webhook=webhook, name=name, value=value)
                    )

            if len(headers_to_create) > 0:
                TableWebhookHeader.objects.bulk_create(headers_to_create)

        # Invalidate the prefetch objects cache because the related object might have
        # changed.
        webhook._prefetched_objects_cache = {}

        return webhook

    def delete_table_webhook(self, user: DjangoUser, webhook: TableWebhook):
        """
        Deletes an existing table webhook.

        :param user: The user on whose behalf the webhook is deleted.
        :param webhook: The webhook object that must be deleted.
        """

        workspace = webhook.table.database.workspace
        CoreHandler().check_permissions(
            user,
            DeleteWebhookOperationType.type,
            workspace=workspace,
            context=webhook.table,
        )

        webhook.delete()

    def make_request(
        self, method: str, url: str, headers: dict, payload: dict
    ) -> Response:
        """
        Makes a request to the provided URL with the provided settings. In production
        mode, the advocate library is used so that the internal network can't be
        reached.

        :param method: The HTTP request method that must be used.
        :param url: The URL that must called.
        :param headers: The headers that must be sent. The key is the name and the
            value the value.
        :param payload: The JSON pay as dict that must be sent.
        :return: The request and response as the tuple (request, response)
        """

        request = get_webhook_request_function()

        response = request(
            method,
            url,
            headers=headers,
            json=payload,
            timeout=settings.BASEROW_WEBHOOKS_REQUEST_TIMEOUT_SECONDS,
        )

        if response.history:
            # If there is a redirect, response.request will point to the final request
            # in the request chain. Make sure we get the first request.
            first_request = response.history[0].request
        else:
            first_request = response.request

        return first_request, response

    def get_headers(self, event_type: str, event_id: str):
        """Returns the default headers that must be added to every request."""

        return {
            "Content-type": "application/json",
            "X-Baserow-Event": event_type,
            "X-Baserow-Delivery": str(event_id),
        }

    def trigger_test_call(
        self,
        user: DjangoUser,
        table: Table,
        event_type: str,
        headers: Optional[dict] = None,
        **kwargs: dict,
    ):
        """
        Helps with running a manual test call triggered by the user. It will generate
        an event_id, as well as uses a "manual.call" event type to indicate that this
        was a user generated call.

        :param user: The user on whose behalf the test call is trigger.
        :param table: The table for which the test call must be triggered.
        :param event_type: The event type that must triggered.
        :param headers: The additional headers that must be added. The key is the
            name and the value the value.
        :param kwargs: Additional table webhook arguments that will be used like the
            url, use_user_field_names etc.
        """

        if not headers:
            headers = {}

        workspace = table.database.workspace
        CoreHandler().check_permissions(
            user,
            TestTriggerWebhookOperationType.type,
            workspace=workspace,
            context=table,
        )

        allowed_fields = [
            "use_user_field_names",
            "url",
            "request_method",
            "name",
            "include_all_events",
        ]
        values = extract_allowed(kwargs, allowed_fields)
        webhook = TableWebhook(table=table, **values)  # Must not be saved.

        event_id = str(uuid.uuid4())
        model = table.get_model()

        event = webhook_event_type_registry.get(event_type)

        payload = event.get_test_call_payload(table, model, event_id, webhook)
        headers.update(self.get_headers(event_type, event_id))

        return self.make_request(webhook.request_method, webhook.url, headers, payload)

    def format_request(self, request: PreparedRequest) -> str:
        """
        Helper function, which will format a requests request object.
        """

        return "{}\r\n{}\r\n\r\n{}".format(
            request.method + " " + request.url,
            "\r\n".join("{}: {}".format(k, v) for k, v in request.headers.items()),
            json.dumps(json.loads(request.body or "{}"), indent=4),
        )

    def format_response(self, response: Response) -> str:
        """
        Helper function, which will format a requests response. It will try to format
        the response body as json and if it is not a valid json it will fallback to
        text.
        """

        try:
            response_body = response.json()
            response_body = json.dumps(response_body, indent=4)
        except Exception:
            response_body = response.text

        return "{}\r\n\r\n{}".format(
            "\r\n".join("{}: {}".format(k, v) for k, v in response.headers.items()),
            response_body,
        )

    def clean_webhook_calls(self, webhook: TableWebhook):
        """
        Cleans up oldest webhook calls and makes sure that the total amount of calls
        will never exceed the `BASEROW_WEBHOOKS_MAX_CALL_LOG_ENTRIES` setting.

        :param webhook: The webhook for which the calls must be cleaned up.
        """

        calls_to_keep = (
            TableWebhookCall.objects.filter(webhook=webhook)
            .order_by("-called_time")
            .values_list("id", flat=True)[
                : settings.BASEROW_WEBHOOKS_MAX_CALL_LOG_ENTRIES
            ]
        )
        TableWebhookCall.objects.filter(
            ~Q(id__in=calls_to_keep), webhook=webhook
        ).delete()

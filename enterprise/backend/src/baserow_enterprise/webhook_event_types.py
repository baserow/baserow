from django.conf import settings
from django.db.models import Q

from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.api.views.serializers import ViewSerializer
from baserow.contrib.database.views.handler import ViewSubscriptionHandler
from baserow.contrib.database.views.models import GridView
from baserow.contrib.database.views.signals import rows_entered_view
from baserow.contrib.database.webhooks.registries import WebhookEventType
from baserow_enterprise.features import ADVANCED_WEBHOOKS


class EnterpriseWebhookEventType(WebhookEventType):
    def listener(self, **kwargs: dict):
        """
        Only calls the super listener if the workspace has a valid license.
        """

        table = self.get_table_object(**kwargs)
        if LicenseHandler.workspace_has_feature(
            ADVANCED_WEBHOOKS, table.database.workspace
        ):
            super().listener(**kwargs)


class RowsEnterViewEventType(EnterpriseWebhookEventType):
    type = "view.rows_entered"
    signal = rows_entered_view
    should_trigger_when_all_event_types_selected = False

    def get_table_object(self, model, **kwargs):
        return model.baserow_table

    def get_filters_for_webhooks_to_call(self, view, **kwargs: dict) -> Q:
        """
        Filters to pass to WebhookHandler.find_webhooks_to_call to find the webhooks
        that need to be called for the table. By default it will filter on the event
        type and the table id. This method can be overwritten to add additional filters
        to the query.

        :param kwargs: The arguments of the signal.
        :return: A Q object containing the filters to pass to the query.
        """

        q = Q(events__event_type__in=[self.type]) & Q(events__views=view)

        table = self.get_table_object(**kwargs)
        return q & Q(table_id=table.id, active=True)

    def serialize_rows(self, model, rows, use_user_field_names):
        rows_serializer = get_row_serializer_class(
            model,
            RowSerializer,
            is_response=True,
            user_field_names=use_user_field_names,
        )
        return rows_serializer(rows, many=True).data

    def serialize_view(self, view):
        return ViewSerializer(view).data

    def _paginate_payload(self, webhook, event_id, payload):
        """
        Paginates the payload if it's too large. This is done by splitting the rows
        into multiple payloads and returning a list of them. This method also replaces
        the row_ids with the actual row data.
        """

        row_ids = payload.pop("row_ids")
        batch_size = settings.BASEROW_WEBHOOK_ROWS_ENTER_VIEW_BATCH_SIZE
        current_batch_row_ids = row_ids[:batch_size]
        if len(current_batch_row_ids) < payload["total_count"]:
            payload["offset"] = (payload.get("batch_id", 1) - 1) * batch_size
            payload["batch_size"] = len(current_batch_row_ids)

        # prepare the remaining payload with the other row ids for the next batch
        remaining = None
        if len(row_ids) > batch_size:
            remaining = payload.copy()
            remaining["row_ids"] = row_ids[batch_size:]

        # get_payload only serialized row_ids, but since this method runs in the
        # celery worker, we have more time to fully serialize fields data.
        table = webhook.table
        model = table.get_model()

        row_fields = [
            field.name if webhook.use_user_field_names else field.db_column
            for field in model.get_fields()
        ]
        payload["fields"] = ["id", "order", *row_fields]

        rows = model.objects_and_trash.filter(
            id__in=current_batch_row_ids
        ).enhance_by_fields()
        payload["rows"] = self.serialize_rows(model, rows, webhook.use_user_field_names)

        return payload, remaining

    def get_test_call_payload(self, table, model, event_id, webhook):
        view = GridView(id=0, name="View", table=table, order=1)
        row = model(id=0, order=0)
        payload = self.get_payload(
            event_id=event_id, webhook=webhook, view=view, row_ids=[row.id]
        )
        return payload

    def get_payload(self, event_id, webhook, view, row_ids, **kwargs):
        payload = super().get_payload(event_id, webhook, **kwargs)
        payload["view"] = self.serialize_view(view)
        payload["row_ids"] = row_ids
        payload["total_count"] = len(row_ids)

        return payload

    def after_update(self, webhook_event):
        # This is called also during webhook creation, when setting the
        # webhook_event_config
        subscribed_views = ViewSubscriptionHandler.get_subscribed_views(webhook_event)
        requested_views = webhook_event.views.all()

        subscriptions_to_add = set(requested_views) - set(subscribed_views)
        if subscriptions_to_add:
            # Automatically initialize the current rows in the views subscriptions
            ViewSubscriptionHandler.subscribe_to_views(
                webhook_event, list(subscriptions_to_add)
            )

        subscriptions_to_delete = set(subscribed_views) - set(requested_views)
        if subscriptions_to_delete:
            ViewSubscriptionHandler.unsubscribe_from_views(
                webhook_event, list(subscriptions_to_delete)
            )

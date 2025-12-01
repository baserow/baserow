from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.db.models import Q

from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
    remap_serialized_rows_to_user_field_names,
    serialize_rows_for_response,
)
from baserow.contrib.database.fields.field_types import LinkRowFieldType
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.webhooks.models import TableWebhook
from baserow.contrib.database.webhooks.registries import WebhookEventType
from baserow.contrib.database.ws.rows.signals import serialize_rows_values

from .signals import rows_created, rows_deleted, rows_updated


class RespectSendWebhookEvents:
    def listener(self, **kwargs: dict):
        """
        The method that is called when the signal is triggered. By default it will
        wait for the transition to commit to call the `listener_after_commit` method.

        :param kwargs: The arguments of the signal.
        """

        # Don't do anything if `send_webhook_events` is provided and `false` because
        # then the webhook must not be triggered.
        if kwargs.get("send_webhook_events", True) is False:
            return

        return super().listener(**kwargs)


class RowsEventType(RespectSendWebhookEvents, WebhookEventType):
    def get_row_serializer(self, webhook, model):
        return get_row_serializer_class(
            model,
            RowSerializer,
            is_response=True,
            user_field_names=webhook.use_user_field_names,
        )

    def get_filters_for_related_webhook_to_call(
        self,
        model: GeneratedTableModel,
        rows: List[GeneratedTableModel],
        updated_fields_ids: List[int] | None = None,
        **kwargs,
    ) -> Q:
        """
        Returns a Q that can be used to filter webhooks for related tables that contain
        rows that have been updated due to the current event. This is used to trigger
        webhooks for related tables when a link row field in the current table is
        updated, causing the related table to be updated as well.

        :param model: The model of the current table.
        :param updated_fields_ids: The ids of the fields that have been updated. If
            None, all fields will be considered.
        :return: A Q object that can be used to filter webhooks for related tables.
        """

        table = model.baserow_table
        table_field_objs = model.get_field_objects()
        link_row_fields = [
            fo["field"]
            for fo in table_field_objs
            if fo["type"].type == LinkRowFieldType.type
        ]

        updated_table_ids = set()
        updated_field_ids = set()

        for link_row_field in link_row_fields:
            skip_field_update = (
                updated_fields_ids is not None
                and link_row_field.id not in updated_fields_ids
            )
            if skip_field_update:
                continue

            no_related_field_in_linked_table = (
                link_row_field.link_row_table_id == table.id
                or link_row_field.link_row_related_field_id is None
            )
            if no_related_field_in_linked_table:
                continue

            related_field_id = link_row_field.link_row_related_field_id
            related_table = link_row_field.link_row_table
            rows_with_changes = self.get_related_table_row_ids_with_changes(
                related_table, rows, kwargs.get("old_items", None)
            )
            if not rows_with_changes:
                continue

            # At least one row in the related table have been updated
            updated_table_ids.add(related_table.id)
            updated_field_ids.add(related_field_id)

        if updated_table_ids:
            # Include webhooks from linked tables updated by the current event
            related_q = Q(events__event_type=RowsUpdatedEventType.type) & (
                Q(events__fields__in=list(updated_field_ids))
                | Q(events__fields__isnull=True)
            )
            related_q |= Q(include_all_events=True)
            related_q &= Q(table_id__in=list(updated_table_ids), active=True)
        else:
            related_q = Q(id__in=[])  # No webhooks to call for related tables

        return related_q

    def get_payload_for_related_webhook(
        self, event_id: str, webhook: TableWebhook, row_ids: List[int], **kwargs
    ) -> Dict[str, Any]:
        """
        Returns the payload for rows updated in the related table. Because the number of
        rows can be large, we just set the `item_ids` in the payload and let the celery
        task handle the data retrieval from the database from the related model and the
        pagination.

        :param event_id: The id of the event.
        :param webhook: The webhook object related to the call.
        :param row_ids: The ids of the rows that have been updated in the related table.
        :param kwargs: The arguments of the signal.
        :return: The payload for the rows updated in the related table.
        """

        payload = super().get_payload(
            event_id, webhook, event_type=RowsUpdatedEventType.type, **kwargs
        )

        payload["item_ids"] = row_ids
        payload["total_count"] = len(row_ids)
        return payload

    def get_related_table_row_ids_with_changes(
        self,
        related_table: Table,
        rows: List[GeneratedTableModel],
        old_items: List[Dict[str, Any]] | None = None,
    ) -> List[int]:
        """
        Identify rows in the related table that have changed due to the current event.
        For each link row field with a related field in `related_model`, compare the
        current and previous values. If differences are found, add the related table
        row IDs to the list of changed rows.

        :param related_table: The related table to check for changes.
        :param rows: The rows that have been updated in the current table.
        :param old_items: The previous values of the rows that have been updated.
        :return: A list of row IDs in the related table that have changed.
        """

        model = rows[0]._meta.model
        table_field_objs = model.get_field_objects()

        link_row_fields = [
            fo["field"]
            for fo in table_field_objs
            if (
                fo["type"].type == LinkRowFieldType.type
                and fo["field"].link_row_related_field_id is not None
                and fo["field"].link_row_table_id == related_table.id
            )
        ]

        if not old_items:
            old_items = [{}] * len(rows)

        related_row_ids = set()
        for row, old_item in zip(rows, old_items):
            for link_row_field in link_row_fields:
                row_value = [v.id for v in getattr(row, link_row_field.db_column).all()]
                old_row_value = [
                    v["id"] for v in old_item.get(link_row_field.db_column, [])
                ]
                related_row_ids.update(
                    set(row_value).difference(old_row_value)
                    | set(old_row_value).difference(row_value)
                )

        return list(related_row_ids)

    def _paginate_payload(
        self, webhook: TableWebhook, event_id: str, payload: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
        """
        Paginates the payload if it's too large. This is done by splitting the rows
        into multiple payloads and returning a list of them. This method also replaces
        the row_ids with the actual row data.
        """

        key = "item_ids"
        row_ids = payload.pop(key, None)
        if row_ids is None:  # already serialized
            return payload, None

        batch_size = settings.BATCH_ROWS_SIZE_LIMIT
        current_batch_row_ids = row_ids[:batch_size]
        if len(current_batch_row_ids) < payload["total_count"]:
            payload["offset"] = (payload.get("batch_id", 1) - 1) * batch_size
            payload["batch_size"] = len(current_batch_row_ids)

        # prepare the remaining payload with the other row ids for the next batch
        remaining = None
        if len(row_ids) > batch_size:
            remaining = payload.copy()
            remaining[key] = row_ids[batch_size:]

        table = webhook.table
        table_model = table.get_model()

        rows = table_model.objects_and_trash.filter(
            id__in=current_batch_row_ids
        ).enhance_by_fields()
        row_serializer = self.get_row_serializer(webhook, table_model)
        payload["items"] = row_serializer(rows, many=True).data

        return payload, remaining

    def _get_filters_for_webhooks_to_call(
        self, model: GeneratedTableModel, table: Table, **kwargs
    ) -> Q:
        """
        Returns the default filters. This method can be overwritten to add additional
        filters or customize the logic.
        """

        return super().get_filters_for_webhooks_to_call(
            model=model, table=table, **kwargs
        )

    def get_filters_for_webhooks_to_call(
        self, model: GeneratedTableModel, table: Table, **kwargs
    ) -> Q:
        """
        Retrieves the filters for the current table and checks for any changes in tables
        linked via link row fields. If changes are detected, the corresponding filters
        are also included in the query.

        :param model: The model of the current table.
        :param table: The current table.
        :param kwargs: The arguments of the signal.
        :return: A Q object that can be used to filter webhooks for the current table.
        """

        q = self._get_filters_for_webhooks_to_call(model=model, table=table, **kwargs)

        if kwargs.get("rows") is not None:
            q |= self.get_filters_for_related_webhook_to_call(
                model=model, table=table, **kwargs
            )

        return q

    def get_default_payload(
        self,
        event_id: str,
        webhook: TableWebhook,
        model: GeneratedTableModel,
        table: Table,
        rows: List[GeneratedTableModel],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generates the default payload for events originating in the webhook's table.

        :param event_id: The id of the event.
        :param webhook: The webhook object related to the call.
        :param model: The model of the current table.
        :param table: The current table.
        :param rows: The rows that have been updated in the current table.
        :param kwargs: The arguments of the signal.
        :return: The payload for the event.
        """

        payload = super().get_payload(
            event_id, webhook, model=model, table=table, rows=rows, **kwargs
        )
        payload["items"] = self.get_row_serializer(webhook, model)(rows, many=True).data

        if (old_items := kwargs.get("old_items", None)) is not None:
            if webhook.use_user_field_names:
                old_items = remap_serialized_rows_to_user_field_names(old_items, model)
            payload["old_items"] = old_items
        return payload

    def get_related_table_payload(
        self,
        event_id: str,
        webhook: TableWebhook,
        model: GeneratedTableModel,
        rows: List[GeneratedTableModel],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generates the payload for events originating in a related table.

        :param event_id: The id of the event.
        :param webhook: The webhook object related to the call.
        :param model: The model of the table where the event originated.
        :param rows: The rows that have been updated by the current event.
        :param kwargs: The arguments of the signal.
        :return: The payload for the event.
        """

        related_table = webhook.table
        related_table_rows_changed = self.get_related_table_row_ids_with_changes(
            related_table, rows, kwargs.get("old_items", None)
        )
        payload = self.get_payload_for_related_webhook(
            event_id, webhook, related_table_rows_changed
        )
        return payload

    def get_payload(
        self,
        event_id: str,
        webhook: TableWebhook,
        model: GeneratedTableModel,
        table: Table,
        rows: List[GeneratedTableModel],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Serialize the rows and return the payload for the webhook. If the webhook is for
        the current table, return the default payload. If the webhook is for a related
        table, prepare the payload for the rows in the related table that need to notify
        by the webhook, but let the celery task handle the data retrieval from the
        database and the pagination.

        :param event_id: The id of the event.
        :param webhook: The webhook object related to the call.
        :param model: The model of the current table.
        :param table: The current table.
        :param rows: The rows that have been updated in the current table.
        :param kwargs: The arguments of the signal.
        :return: The payload for the event.
        """

        before_return = kwargs.get("before_return", {})
        old_items = dict(before_return).get(serialize_rows_values, None)

        if webhook.table_id == table.id:
            return self.get_default_payload(
                event_id,
                webhook,
                model=model,
                table=table,
                rows=rows,
                old_items=old_items,
                **kwargs,
            )
        else:  # send updates to the related table
            return self.get_related_table_payload(
                event_id,
                webhook,
                model=model,
                table=table,
                rows=rows,
                old_items=old_items,
                **kwargs,
            )


class RowsCreatedEventType(RowsEventType):
    type = "rows.created"
    signal = rows_created

    def get_test_call_payload(self, table, model, event_id, webhook):
        rows = [model(id=0, order=0)]
        payload = self.get_payload(
            event_id=event_id,
            webhook=webhook,
            model=model,
            table=table,
            rows=rows,
        )
        return payload


class RowsUpdatedEventType(RowsEventType):
    type = "rows.updated"
    signal = rows_updated

    def _get_filters_for_webhooks_to_call(self, table: Table, **kwargs) -> Q:
        """
        Only return webhooks of this type for this table that:
         -- are specifically for any of the updated fields if the webhook specifies them
         -- are for any change on any fields if the webhook does not specify any or
         -- the webhook has include all events set to true

        :param table: The table to filter the webhooks for.
        :param kwargs: The arguments of the signal.
        :return: A Q object that can be used to filter webhooks for the current table.
        """

        updated_field_ids = kwargs.get("updated_field_ids", None)
        if updated_field_ids is not None:
            filter_field_ids = Q(events__fields__in=updated_field_ids)
        else:
            filter_field_ids = Q()

        q = Q(events__event_type__in=[self.type]) & (
            filter_field_ids | Q(events__fields__isnull=True)
        )
        q |= Q(include_all_events=True)

        return q & Q(table_id=table.id, active=True)

    def get_test_call_payload(self, table, model, event_id, webhook):
        rows = [model(id=0, order=0)]
        before_return = {
            serialize_rows_values: serialize_rows_for_response(rows, model)
        }
        payload = self.get_payload(
            event_id=event_id,
            webhook=webhook,
            model=model,
            table=table,
            rows=rows,
            before_return=before_return,
            updated_field_ids=None,
        )
        return payload


class RowsDeletedEventType(RowsEventType):
    type = "rows.deleted"
    signal = rows_deleted

    def get_default_payload(self, event_id, webhook, table, model, rows, **kwargs):
        payload = WebhookEventType.get_payload(self, event_id, webhook, **kwargs)
        payload["row_ids"] = [row.id for row in rows]
        return payload

    def get_test_call_payload(self, table, model, event_id, webhook):
        rows = [model(id=0, order=0)]

        payload = self.get_payload(
            event_id=event_id,
            webhook=webhook,
            model=model,
            table=table,
            rows=rows,
        )
        return payload

import uuid

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.dispatch.dispatcher import Signal

from baserow.contrib.database.table.models import Table
from baserow.core.registry import Instance, ModelRegistryMixin, Registry

from .exceptions import SkipWebhookCall
from .tasks import call_webhook


class WebhookEventType(Instance):
    """
    This class represents a custom webhook event type that can be added to the webhook
    event type registry. Each registered event type needs to set a django signal on
    which it will listen on. Upon initialization the webhook event type will connect
    to the django signal.

    The 'listener' function will be called for every received signal. The listener will
    generate a unique ID for every received signal, find all webhooks that need to be
    called and subsequently generates the payload for every webhook and runs a celery
    task that will do the actually call to the endpoint.
    """

    signal = None
    should_trigger_when_all_event_types_selected = True

    def __init__(self):
        if not isinstance(self.signal, Signal):
            raise ImproperlyConfigured(
                "The `signal` property must be set on webhook event types."
            )

        super().__init__()
        self.signal.connect(self.listener)

    def get_test_call_payload(self, table, model, event_id, webhook):
        """
        Constructs a test payload for a webhook call.

        :param table: The table with changes.
        :param model: The table's model.
        :param event_id: The id of the event.
        :param webhook: The webhook object related to the call.
        :return: A JSON serializable dict with the test payload.
        """

        row = model(id=0, order=0)
        payload = self.get_payload(
            event_id=event_id,
            webhook=webhook,
            model=model,
            table=table,
            row=row,
            before_return=None,
        )
        return payload

    def get_payload(self, event_id, webhook, **kwargs):
        """
        The default payload of the event type. This method can be overwritten in
        favor of additional values must be included in the payload.

        :param event_id: The unique uuid event id.
        :param webhook: The webhook object related to call.
        :param kwargs: Additional kwargs related to the signal arguments.
        :return: A JSON serializable dict containing the base payload.
        """

        return {
            "table_id": webhook.table_id,
            "database_id": webhook.table.database_id,
            "workspace_id": webhook.table.database.workspace_id,
            "event_id": str(event_id),
            "event_type": self.type,
        }

    def get_table_object(self, **kwargs: dict) -> Table:
        """
        By default we expect the `table` instance to be in the payload of the signal.
        This method must be overwritten if the table can be extracted in a different
        from.

        :param kwargs: The arguments of the signal.
        :return: The extracted table object.
        """

        table = kwargs.get("table", None)

        if not isinstance(table, Table):
            raise ValueError(
                "Could not extract the table object from the payload of the signal. "
                "Please overwrite the `get_table_object` method."
            )

        return table

    def listener(self, **kwargs: dict):
        """
        The method that is called when the signal is triggered. By default it will
        wait for the transition to commit to call the `listener_after_commit` method.

        :param kwargs: The arguments of the signal.
        """

        transaction.on_commit(lambda: self.listener_after_commit(**kwargs))

    def listener_after_commit(self, **kwargs):
        """
        Called after the signal is triggered and the transaction commits. By default it
        will figure out which webhooks need to be called and will trigger the async task
        that will actually do so.

        :param kwargs: The arguments of the signal.
        """

        from baserow.contrib.database.webhooks.handler import WebhookHandler

        if not kwargs.get("send_webhooks_events", True):
            return

        table = self.get_table_object(**kwargs)
        webhook_handler = WebhookHandler()
        webhooks = webhook_handler.find_webhooks_to_call(table.id, self.type)
        event_id = uuid.uuid4()
        for webhook in webhooks:
            try:
                payload = self.get_payload(event_id, webhook, **kwargs)
                headers = webhook.header_dict
                headers.update(**webhook_handler.get_headers(self.type, event_id))
                call_webhook.delay(
                    webhook_id=webhook.id,
                    event_id=str(event_id),
                    event_type=self.type,
                    method=webhook.request_method,
                    url=webhook.url,
                    headers=headers,
                    payload=payload,
                )
            # Raised if the webhook should be skipped for whatever reason. In that case
            # we don't want to fail, but rather don't do anything.
            except SkipWebhookCall:
                pass


class WebhookEventTypeRegistry(ModelRegistryMixin, Registry):
    name = "webhook_event"


webhook_event_type_registry = WebhookEventTypeRegistry()

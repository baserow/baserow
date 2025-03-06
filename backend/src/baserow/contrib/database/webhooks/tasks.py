from copy import deepcopy
from datetime import datetime, timezone

from django.conf import settings
from django.core import cache
from django.db import transaction
from django.db.utils import OperationalError

from loguru import logger

from baserow.config.celery import app
from baserow.contrib.database.webhooks.exceptions import WebhookPayloadTooLarge
from baserow.contrib.database.webhooks.notification_types import (
    WebhookPayloadTooLargeNotificationType,
)
from baserow.core.redis import RedisQueue


def get_queue(webhook_id):
    queue_key = f"webhook_{webhook_id}_queue"
    redis_connection = cache.cache.client.get_client()
    return RedisQueue(
        queue_key,
        redis_connection,
        max_length=settings.BASEROW_MAX_WEBHOOK_CALLS_IN_QUEUE_PER_WEBHOOK,
    )


def enqueue_webhook_task(webhook_id, event_id, args, kwargs):
    queue = get_queue(webhook_id)
    result = queue.enqueue_task({"args": args, "kwargs": kwargs})

    if result is False:
        logger.warning(
            f"Webhook call {event_id} is not enqueued because webhook id "
            f"{webhook_id} reached the limit of {queue.max_length}."
        )


def clear_webhook_queue(webhook_id):
    queue = get_queue(webhook_id)
    queue.clear()


def schedule_next_task_in_queue(webhook_id):
    next_task = get_queue(webhook_id).get_and_pop_next()
    if next_task:
        call_webhook.delay(*next_task["args"], **next_task["kwargs"])


@app.task(
    bind=True,
    max_retries=settings.BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL,
    queue="export",
)
def call_webhook(
    self,
    webhook_id: int,
    event_id: str,
    event_type: str,
    method: str,
    url: str,
    headers: dict,
    payload: dict,
    retries: int = 0,
    **kwargs: dict,
):
    """
    This task should be called asynchronously when the webhook call must be trigged.
    All the raw values should be provided as argument. If the call fails for whatever
    reason, it tries again until the max retries have been reached.

    It also makes sure that only one webhook call can be triggered concurrently. Is
    more are triggered, then they're added to the queue, and delayed when current one
    completes.

    :param webhook_id: The id of the webhook related to the call.
    :param event_id: A unique event id that can used as id for the table webhook call
        model.
    :param event_type: The event type related to the webhook trigger.
    :param method: The request method the must be used.
    :param url: The URL can must be called.
    :param headers: The additional headers that must be added to the request. The key
        is the name and the value is the value.
    :param payload: The JSON serializable payload that must be used as request body.
    :param retries: Because the task can be added to a queue, we can't on the
        self.request.retries value. We're therefore passing in the kwargs so that we
        can still measure this.
    """

    from .models import TableWebhook
    from .registries import webhook_event_type_registry

    if self.request.retries > retries:
        retries = self.request.retries

    try:
        with transaction.atomic():
            try:
                webhook = TableWebhook.objects.select_for_update(
                    of=("self",), nowait=True
                ).get(id=webhook_id, active=True)
            except TableWebhook.DoesNotExist:
                # If the webhook has been deleted or disabled while executing, we don't
                # want to continue making calls the URL because we can't update the
                # state of the webhook. We're also clearing the queue because the
                # other calls don't have to be executed anymore.
                transaction.on_commit(lambda: clear_webhook_queue(webhook_id))
                return
            except OperationalError as e:
                if "could not obtain lock" in e.args[0]:
                    # If a lock could not be obtained, it means that another call for
                    # this webhook is being made at the moment. In that case,
                    # we'll enqueue the webhook call, so that it's executed later.
                    # This makes sure that only a maximum one webhook call is
                    # triggered concurrently.
                    args = self.request.args
                    kwargs = self.request.kwargs
                    enqueue_webhook_task(webhook_id, event_id, args, kwargs)
                    return
                else:
                    raise e

            # Paginate the payload if necessary and enqueue the remaining data.
            webhook_event_type = webhook_event_type_registry.get(event_type)
            try:
                payload, remaining = webhook_event_type.paginate_payload(
                    webhook, event_id, deepcopy(payload)
                )
            except WebhookPayloadTooLarge:
                success = True  # We don't want to retry this call, because it will fail again.
                transaction.on_commit(
                    lambda: WebhookPayloadTooLargeNotificationType.notify_admins_in_workspace(
                        webhook, event_id
                    )
                )
            else:
                success = make_request_and_save_result(
                    webhook, event_id, event_type, method, url, headers, payload
                )
                # enqueue the next call if there is still remaining payload
                if success and remaining:
                    args = (
                        webhook_id,
                        event_id,
                        event_type,
                        method,
                        url,
                        headers,
                        remaining,
                    )
                    kwargs = {"retries": 0}
                    enqueue_webhook_task(webhook_id, event_id, args, kwargs)

            # After the transaction successfully commits we can delay the next call
            # in the queue, so that only one call is triggered concurrently.
            transaction.on_commit(lambda: schedule_next_task_in_queue(webhook_id))
    except Exception as e:
        # If something else fails, then we don't want to block the webhook call
        # queue, so we'll delay the next task.
        schedule_next_task_in_queue(webhook_id)
        raise e

    # This part must be outside of the transaction block, otherwise it could cause
    # the transaction to rollback when the retry exception is raised, and we don't want
    # that to happen.
    if not success and retries < settings.BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL:
        # If the task is still operating within the max retries per call limit, then we
        # want to retry the task with an exponential backoff. If there are other
        # webhook calls in the webhook task queue (not the Celery queue), it could be
        # that the task is placed at the end of the queue.
        kwargs = self.request.kwargs or {}
        kwargs["retries"] = retries + 1
        self.retry(countdown=2**retries, kwargs=kwargs)


def make_request_and_save_result(
    webhook, event_id, event_type, method, url, headers, payload
):
    from advocate import UnacceptableAddressException
    from requests import RequestException

    from .handler import WebhookHandler
    from .models import TableWebhookCall
    from .notification_types import WebhookDeactivatedNotificationType

    handler = WebhookHandler()

    request = None
    response = None
    success = False
    error = ""

    try:
        request, response = handler.make_request(method, url, headers, payload)
        success = response.ok
    except RequestException as exception:
        request = exception.request
        response = exception.response
        error = str(exception)
    except UnacceptableAddressException as exception:
        error = f"UnacceptableAddressException: {exception}"

    TableWebhookCall.objects.update_or_create(
        event_id=event_id,
        batch_id=payload.get("batch_id", None),
        event_type=event_type,
        webhook=webhook,
        defaults={
            "called_time": datetime.now(tz=timezone.utc),
            "called_url": url,
            "request": handler.format_request(request) if request is not None else None,
            "response": handler.format_response(response)
            if response is not None
            else None,
            "response_status": response.status_code if response is not None else None,
            "error": error,
        },
    )
    handler.clean_webhook_calls(webhook)

    if success:
        if webhook.failed_triggers != 0:
            # If the call was successful and failed triggers had been increased
            # in the past, we can safely reset it to 0 again to prevent
            # deactivation of the webhook.
            webhook.failed_triggers = 0
            webhook.save()
    elif (
        webhook.failed_triggers
        < settings.BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES
    ):
        # If the task has reached the maximum amount of failed calls, we're
        # going to give up and increase the total failed triggers of the webhook
        # if we're still operating within the limits of the max consecutive
        # trigger failures.
        webhook.failed_triggers += 1
        webhook.save()
    else:
        # If webhook has reached the maximum amount of failed triggers, we're
        # going to deactivate it because we can reasonably assume that the
        # target doesn't listen anymore. At this point we've tried 8 * 10 times.
        # The user can manually activate it again when it's fixed.
        webhook.active = False
        webhook.save()

        # Send a notification to the workspace admins that the webhook was
        # deactivated.
        transaction.on_commit(
            lambda: WebhookDeactivatedNotificationType.notify_admins_in_workspace(
                webhook
            )
        )

    return success

from datetime import datetime, timezone

from django.conf import settings
from django.db import transaction
from django.db.utils import OperationalError

from baserow.config.celery import app


@app.task(
    bind=True,
    # We don't need a max_retries because that logic is handled inside the task.
    max_retries=None,
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
    **kwargs: dict,
):
    """
    This task should be called asynchronously when the webhook call must be trigged.
    All the raw values should be provided as argument. If the call fails for whatever
    reason, it tries again until the max retries have been reached.

    :param webhook_id: The id of the webhook related to the call.
    :param event_id: A unique event id that can used as id for the table webhook call
        model.
    :param event_type: The event type related to the webhook trigger.
    :param method: The request method the must be used.
    :param url: The URL can must be called.
    :param headers: The additional headers that must be added to the request. The key
        is the name and the value is the value.
    :param payload: The JSON serializable payload that must be used as request body.
    """

    from advocate import UnacceptableAddressException
    from requests import RequestException

    from django.core.cache import cache

    from .handler import WebhookHandler
    from .models import TableWebhook, TableWebhookCall

    with transaction.atomic():
        handler = WebhookHandler()

        disabled_cache_key = f"baserow_disabled_webhook_{webhook_id}"
        is_disabled = cache.get(disabled_cache_key, False)

        # If the webhook is disabled via the cache, it means the task has been trying
        # to get a lock on the webhook for too long. To prevent the celery queue from
        # we don't proceed triggering the webhook.
        if is_disabled:
            return

        try:
            webhook = TableWebhook.objects.select_for_update(
                nowait=True,
                of=("self", )
            ).get(
                id=webhook_id,
                # If a webhook is not active, then it should not be executed.
                active=True,
            )
        except TableWebhook.DoesNotExist:
            # If the webhook has been deleted or disabled while executing, we don't want
            # to continue trying to call the URL because we can't update the state of
            # the webhook.
            return
        except OperationalError as e:
            if "could not obtain lock" in e.args[0]:
                if (
                    self.request.retries <
                    settings.BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL
                ):
                    # If the Webhook object is locked, it means that another webhook is
                    # being executed. We only want to allow one webhook trigger to
                    # run concurrently to keep the workers free. we're going to retry
                    # the job later with an exponential backoff.
                    self.retry(countdown=2**self.request.retries)
                else:
                    # If the webhook is still locked after
                    # BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL (default is 8) attempts,
                    # meaning after 2**8-1=255 seconds, then we can safely say that a
                    # lot of webhook calls are triggered. This could even be that the
                    # webhook is stuck in a loop, and because the celery tasks can
                    # pile up, taking memory, we should try to deactivate the webhook.
                    cache.set(
                        disabled_cache_key,
                        True,
                        timeout=2**settings.BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL
                    )
                return
            else:
                raise e

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
            event_type=event_type,
            webhook=webhook,
            defaults={
                "called_time": datetime.now(tz=timezone.utc),
                "called_url": url,
                "request": handler.format_request(request)
                if request is not None
                else None,
                "response": handler.format_response(response)
                if response is not None
                else None,
                "response_status": response.status_code
                if response is not None
                else None,
                "error": error,
            },
        )
        handler.clean_webhook_calls(webhook)

        if success and webhook.failed_triggers != 0:
            # If the call was successful and failed triggers had been increased in
            # the past, we can safely reset it to 0 again to prevent deactivation of
            # the webhook.
            webhook.failed_triggers = 0
            webhook.save()
        elif not success and (
            webhook.failed_triggers
            < settings.BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES
        ):
            # If the task has reached the maximum amount of failed calls, we're going to
            # give up and increase the total failed triggers of the webhook if we're
            # still operating within the limits of the max consecutive trigger failures.
            webhook.failed_triggers += 1
            webhook.save()
        elif not success:
            # If webhook has reached the maximum amount of failed triggers,
            # we're going to deactivate it because we can reasonable assume that the
            # target doesn't listen anymore. At this point we've tried 8 * 10 times.
            # The user can manually activate it again when it's fixed.
            webhook.active = False
            webhook.save()

        # If the webhook was disabled via the cache in the meantime, then we should
        # mark it as deactivated because we're the one with the lock and this webhook
        # is supposed to be disabled.
        if cache.get(disabled_cache_key, False):
            webhook.active = False
            webhook.save()

    # This part must be outside of the transaction block, otherwise it could cause
    # the transaction to rollback when the retry exception is raised, and we don't want
    # that to happen.
    if (
        not success
        and self.request.retries < settings.BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL
    ):
        # If the task is still operating within the max retries per call limit,
        # then we want to retry the task with an exponential backoff.
        self.retry(countdown=2**self.request.retries)

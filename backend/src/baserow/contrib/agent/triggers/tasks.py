from baserow.config.celery import app


@app.task
def start_trigger_conversation(
    trigger_id: int, content: str, failure: str | None
) -> None:
    """
    Start the conversation of a trigger that fired, after the event that fired it
    committed.

    :param trigger_id: The id of the trigger that fired.
    :param content: The resolved message opening the conversation.
    :param failure: The error code failing the reply instead of running it, or None.
    """

    from .dispatcher import agent_trigger_dispatcher

    agent_trigger_dispatcher.start(trigger_id, content, failure)

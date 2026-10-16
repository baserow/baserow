def stopped_after(done: int, total: int) -> str:
    """
    Describes a call that stopped between items because its run was cancelled.
    The tool keeps the finished items instead of rolling them back.

    :param done: How many items the call finished.
    :param total: How many items the call asked for.
    :return: The note the tool returns under `stopped`.
    """

    return (
        f"Stopped after {done} of {total} items because the run was cancelled. "
        "The finished items were kept; the others were not processed."
    )

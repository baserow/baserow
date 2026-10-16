from rest_framework.status import (
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
)

ERROR_CHAT_RUN_DOES_NOT_EXIST = (
    "ERROR_CHAT_RUN_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested run does not exist or is not accessible.",
)

ERROR_CHAT_RUN_IN_PROGRESS = (
    "ERROR_CHAT_RUN_IN_PROGRESS",
    HTTP_409_CONFLICT,
    "The previous message in this chat is still being answered.",
)

ERROR_CHAT_RUN_LIMIT = (
    "ERROR_CHAT_RUN_LIMIT",
    HTTP_429_TOO_MANY_REQUESTS,
    "Too many of your messages are being answered at once. Try again when one "
    "of them is done.",
)

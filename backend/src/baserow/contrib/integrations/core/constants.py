from django.db import models


class HTTP_METHOD(models.TextChoices):
    GET = "GET", "GET"
    POST = "POST", "POST"
    PUT = "PUT", "PUT"
    DELETE = "DELETE", "DELETE"
    PATCH = "PATCH", "PATCH"
    HEAD = "HEAD", "HEAD"
    OPTIONS = "OPTIONS", "OPTIONS"


class BODY_TYPE(models.TextChoices):
    JSON = "json", "JSON"
    FORM = "form", "Form Data"
    RAW = "raw", "Raw"
    NONE = "none", "None"


class CSV_FILE_READER_INPUT_TYPE(models.TextChoices):
    FILE = "file", "File"
    CONTENT = "content", "Content"


PERIODIC_INTERVAL_MINUTE = "MINUTE"
PERIODIC_INTERVAL_HOUR = "HOUR"
PERIODIC_INTERVAL_DAY = "DAY"
PERIODIC_INTERVAL_WEEK = "WEEK"
PERIODIC_INTERVAL_MONTH = "MONTH"
PERIODIC_INTERVAL_CHOICES = [
    (PERIODIC_INTERVAL_MINUTE, PERIODIC_INTERVAL_MINUTE),
    (PERIODIC_INTERVAL_HOUR, PERIODIC_INTERVAL_HOUR),
    (PERIODIC_INTERVAL_DAY, PERIODIC_INTERVAL_DAY),
    (PERIODIC_INTERVAL_WEEK, PERIODIC_INTERVAL_WEEK),
    (PERIODIC_INTERVAL_MONTH, PERIODIC_INTERVAL_MONTH),
]

# Services created before the schedule became timezone aware stored their fields
# already converted to UTC, so UTC is the default which keeps them running at
# exactly the same instants.
PERIODIC_TIMEZONE_DEFAULT = "UTC"

SMTP_EMAIL_TIMEOUT = 30

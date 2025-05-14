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

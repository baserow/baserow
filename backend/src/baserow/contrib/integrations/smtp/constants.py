from django.db import models


class MAIL_BODY_TYPE(models.TextChoices):
    TEXT = "text", "TEXT"
    HTML = "html", "HTML"

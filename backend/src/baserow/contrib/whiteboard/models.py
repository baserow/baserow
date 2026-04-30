from django.db import models

from baserow.core.models import Application

__all__ = ["Whiteboard"]


class Whiteboard(Application):
    content = models.JSONField(default=dict, blank=True)

    def get_parent(self):
        return self.application_ptr

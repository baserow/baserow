from django.db import models
from django.db.models import Q

from django_cte import CTEQuerySet


class UserFileQuerySet(CTEQuerySet, models.QuerySet):
    def name(self, *names):
        if len(names) == 0:
            raise ValueError("At least one name must be provided.")

        q_or = Q()

        for name in names:
            q_or |= Q(**self.model.deconstruct_name(name))

        return self.filter(q_or)

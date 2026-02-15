from django.db import models
from django.db.models import Q

from django_cte import CTEQuerySet

from .exceptions import InvalidUserFileNameError


class UserFileQuerySet(CTEQuerySet, models.QuerySet):
    def name(self, *names):
        """
        Filter UserFile objects by their generated names.
        
        :param names: One or more generated file names to filter by
        :return: Filtered queryset
        :raises ValueError: If no names are provided
        :raises InvalidUserFileNameError: If any name is not in the correct format
        """
        if len(names) == 0:
            raise ValueError("At least one name must be provided.")

        q_or = Q()

        for name in names:
            try:
                deconstructed = self.model.deconstruct_name(name)
                q_or |= Q(**deconstructed)
            except InvalidUserFileNameError as e:
                # Re-raise with more context
                raise InvalidUserFileNameError(
                    name,
                    f"Cannot query for file with invalid name format: {name}. "
                    f"Expected format: 'unique_hash.extension' with alphanumeric characters."
                )

        return self.filter(q_or)

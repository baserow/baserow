from django.db import models
from django.db.models import Q

from django_cte import CTEQuerySet

from .template_files import TEMPLATE_FILE_UNIQUE_PATTERN, template_file_prefix


class UserFileQuerySet(CTEQuerySet, models.QuerySet):
    def name(self, *names):
        if len(names) == 0:
            raise ValueError("At least one name must be provided.")

        q_or = Q()

        for name in names:
            q_or |= Q(**self.model.deconstruct_name(name))

        return self.filter(q_or)

    def template_files(self, workspace_id=None):
        """
        Filters on the files of user templates.

        :param workspace_id: The id of the template workspace, or None for the files
            of every template.
        """

        if workspace_id is None:
            return self.filter(unique__regex=TEMPLATE_FILE_UNIQUE_PATTERN)
        return self.filter(unique__startswith=template_file_prefix(workspace_id))

    def exclude_template_files(self):
        return self.exclude(unique__regex=TEMPLATE_FILE_UNIQUE_PATTERN)

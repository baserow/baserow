from django.db import models


class FieldDependency(models.Model):
    """
    A FieldDependency represents a dependency between two Fields or a single Field
    depending on a field name which doesn't exist as a field yet.
    """

    dependant = models.ForeignKey(
        "database.Field",
        on_delete=models.CASCADE,
        related_name="dependencies",
    )
    dependency = models.ForeignKey(
        "database.Field",
        on_delete=models.CASCADE,
        related_name="dependants",
        null=True,
        blank=True,
    )
    # The link row field that the dependant depends on the dependency via.
    via = models.ForeignKey(
        "database.LinkRowField",
        on_delete=models.CASCADE,
        related_name="vias",
        null=True,
        blank=True,
    )
    broken_reference_field_name = models.TextField(null=True, blank=True, db_index=True)

    def _dependency_postfix(self) -> str:
        if self.via_id is not None:
            if self.broken_reference_field_name is not None:
                return f"broken_via__{self.via_id}__{self.broken_reference_field_name}"
            else:
                return f"depends_via__{self.via_id}__on__{self.dependency_id}"
        elif self.broken_reference_field_name is not None:
            return f"broken__{self.broken_reference_field_name}"
        else:
            return f"depends_on__{self.dependency_id}"

    def __str__(self):
        """
        Returns a string representation of FieldDependency which can be compared with
        others to see if two field dependencies are functionally the same.

        :return: A string that represents this dependency.
        """

        return f"{self.dependant_id}__{self._dependency_postfix()}"

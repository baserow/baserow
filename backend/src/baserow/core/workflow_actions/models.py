from django.db import models

from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)
from baserow.core.registry import ModelRegistryMixin


class WorkflowAction(
    PolymorphicContentTypeMixin,
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    TrashableModelMixin,
    models.Model,
    WithRegistry,
):
    @staticmethod
    def get_type_registry() -> ModelRegistryMixin:
        raise Exception(
            "Needs to be implement by module specific workflow actions parent"
        )

    class Meta:
        abstract = True

from django.contrib.auth import get_user_model
from django.db.models.signals import pre_delete

from .handler import delete_personal_views

User = get_user_model()


def before_user_permanently_deleted(sender, instance, **kwargs):
    delete_personal_views(instance.id)


def connect_to_user_pre_delete_signal():
    pre_delete.connect(before_user_permanently_deleted, User)


__all__ = [
    "connect_to_user_pre_delete_signal",
]

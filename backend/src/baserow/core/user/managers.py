from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.db import router, transaction
from django.db.models import Exists, Manager, OuterRef, QuerySet

from asgiref.sync import sync_to_async


def human_profile_exists(user_id_field: str) -> Exists:
    """
    Matches rows whose user is human, as a subquery so row locks stay on the outer rows.

    :param user_id_field: The field of the outer query that holds the user ID.
    :return: The condition to filter the outer query with.
    """

    profile_model = apps.get_model("core", "UserProfile")
    return Exists(
        profile_model.objects_and_trash.filter(
            user_id=OuterRef(user_id_field), user_type=profile_model.UserType.HUMAN
        )
    )


class UsersAndIdentitiesManager(UserManager):
    use_in_migrations = False

    def _create_user(self, username, email, password, **extra_fields):
        using = self._db or router.db_for_write(self.model)
        with transaction.atomic(using=using):
            user = super()._create_user(username, email, password, **extra_fields)
            apps.get_model("core", "UserProfile").objects.using(using).create(user=user)
        return user

    async def _acreate_user(self, username, email, password, **extra_fields):
        return await sync_to_async(self._create_user)(
            username, email, password, **extra_fields
        )


class HumanUserManager(UsersAndIdentitiesManager):
    use_in_migrations = True

    def get_queryset(self) -> QuerySet:
        return super().get_queryset().filter(human_profile_exists("pk"))

    def __eq__(self, other):
        # Migration detection compares instances before serialization.
        if type(other) is UserManager:
            return self._constructor_args == other._constructor_args
        return super().__eq__(other)

    __hash__ = UserManager.__hash__

    def deconstruct(self):
        as_manager, _, queryset_path, args, kwargs = super().deconstruct()
        return (
            as_manager,
            "django.contrib.auth.models.UserManager",
            queryset_path,
            args,
            kwargs,
        )


def human_memberships(manager_class: type[Manager]) -> type[Manager]:
    """
    Narrows a membership manager to human members, so identities need an explicit opt-in.

    :param manager_class: The membership manager class to narrow.
    :return: A manager class that only returns the memberships of human users.
    """

    class HumanMembershipManager(manager_class):
        def get_queryset(self) -> QuerySet:
            return super().get_queryset().filter(human_profile_exists("user_id"))

    return HumanMembershipManager


def install_user_managers() -> None:
    """Keep Django's migration manager unchanged and make runtime queries human-only."""

    user_model = get_user_model()
    if isinstance(user_model.objects, HumanUserManager):
        return
    user_model.add_to_class("objects", HumanUserManager())
    user_model.add_to_class("objects_and_identities", UsersAndIdentitiesManager())

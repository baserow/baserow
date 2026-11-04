from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.db import router, transaction
from django.db.models import Exists, OuterRef, Q, QuerySet

from asgiref.sync import sync_to_async
from django_cte import CTEQuerySet


class PeopleUserQuerySet(QuerySet):
    """People, including disabled people, with valid identity metadata."""

    def __init__(self, model=None, query=None, using=None, hints=None):
        super().__init__(model=model, query=query, using=using, hints=hints)
        if model is not None and query is None:
            from baserow.core.models import UserProfile

            # A subquery keeps ordinary User row locks independent of Profile joins.
            people = UserProfile.objects_and_trash.filter(
                user_id=OuterRef("pk"), identity_type="human"
            )
            self.query.add_q(Q(Exists(people)))


class ProfileUserManager(UserManager):
    """Creates every User together with its profile."""

    use_in_migrations = False

    def _create_user(self, username, email, password, **extra_fields):
        from baserow.core.models import UserProfile

        using = self._db or router.db_for_write(self.model)
        with transaction.atomic(using=using):
            user = super()._create_user(username, email, password, **extra_fields)
            UserProfile.objects.using(using).create(user=user)
        return user

    async def _acreate_user(self, username, email, password, **extra_fields):
        return await sync_to_async(self._create_user)(
            username, email, password, **extra_fields
        )


class IdentityQuerySet(QuerySet):
    def agents(self) -> "IdentityQuerySet":
        return self.filter(profile__identity_type="agent")


class IdentitiesAndTrashManager(ProfileUserManager.from_queryset(IdentityQuerySet)):
    """People and agent identities, including trashed agents."""


class IdentitiesManager(IdentitiesAndTrashManager):
    """People and agent identities, without trashed agents."""

    def get_queryset(self) -> IdentityQuerySet:
        from baserow.core.models import UserProfile

        # A subquery keeps User row locks independent of Profile joins.
        trashed = UserProfile.trash.filter(user_id=OuterRef("pk"))
        return super().get_queryset().filter(~Exists(trashed))


class PeopleUserManager(ProfileUserManager):
    use_in_migrations = True
    _queryset_class = PeopleUserQuerySet

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


class WorkspaceUserQuerySet(CTEQuerySet):
    def people(self):
        return self.filter(user__profile__identity_type="human")

    def agents(self):
        return self.filter(user__profile__identity_type="agent")


def install_user_managers() -> None:
    """Keep Django's migration manager unchanged and opt runtime queries into people."""

    user_model = get_user_model()
    if isinstance(user_model.objects, PeopleUserManager):
        return
    user_model.add_to_class("objects", PeopleUserManager())
    user_model.add_to_class("identities", IdentitiesManager())
    user_model.add_to_class("identities_and_trash", IdentitiesAndTrashManager())

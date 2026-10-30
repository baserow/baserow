from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.db.models import Exists, OuterRef, Q, QuerySet


class PeopleUserQuerySet(QuerySet):
    """The default User queryset, excluding users linked to Agents."""

    def __init__(self, model=None, query=None, using=None, hints=None):
        super().__init__(model=model, query=query, using=using, hints=hints)
        if model is not None and query is None:
            from baserow.core.models import Agent

            # An outer join would prevent locking User rows with FOR UPDATE.
            agents = Agent.objects_and_trash.filter(user_id=OuterRef("pk"))
            self.query.add_q(~Q(Exists(agents)))


class UsersAndAgentsManager(UserManager):
    """All user rows, including the users stored for Agents."""

    use_in_migrations = False


def install_user_managers() -> None:
    """Install the people-only default and explicit inclusive User managers."""

    user_model = get_user_model()
    if user_model.objects._queryset_class is PeopleUserQuerySet:
        return

    # Preserve Django's manager class so the auth migration state stays unchanged.
    people = UserManager()
    people._queryset_class = PeopleUserQuerySet
    user_model.add_to_class("objects", people)
    user_model.add_to_class("objects_and_agents", UsersAndAgentsManager())

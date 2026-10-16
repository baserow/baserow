import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.db.models import Func

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.widgets.models import SummaryWidget, Widget
from baserow.core.models import Application

__all__ = ["Dashboard", "DashboardDataSource", "SummaryWidget", "Widget"]


class RandomSlug(Func):
    """
    Generates a random slug in the database. It is the database default of
    `Dashboard.slug`, so a row inserted without a slug still gets a unique value of
    its own: the rows that exist when the column is added, and rows inserted by the
    previous application version during a zero downtime deployment. Dashboards
    created by this version get their slug from the Python default instead, in the
    same format as database views.
    """

    template = "REPLACE(GEN_RANDOM_UUID()::text, '-', '')"
    output_field = models.CharField()
    arity = 0


class Dashboard(Application):
    description = models.TextField(blank=True, db_default="")
    public = models.BooleanField(
        default=False,
        db_default=False,
        db_index=True,
        help_text="Indicates whether the dashboard is publicly accessible to visitors.",
    )
    slug = models.SlugField(
        default=secrets.token_urlsafe,
        db_default=RandomSlug(),
        unique=True,
        db_index=True,
        help_text="The unique slug where the dashboard can be accessed publicly on.",
    )
    public_password = models.CharField(
        # Sized for the salted hash that Django generates, not for the password the
        # user types. The request serializer validates the raw password length.
        max_length=128,
        blank=True,
        db_default="",
        help_text="The hashed password required to access the public dashboard URL.",
    )
    show_logo = models.BooleanField(
        default=True,
        db_default=True,
        help_text="Indicates whether the Baserow logo is shown on the public "
        "dashboard.",
    )

    def get_parent(self):
        # Parent is the Application here even if it's at the "same" level
        # but it's a more generic type
        return self.application_ptr

    @property
    def public_has_password(self) -> bool:
        """
        Indicates whether the public dashboard is password protected or not.

        :return: True if the public dashboard is password protected, False otherwise.
        """

        return self.public_password != ""  # nosec b105

    def rotate_slug(self):
        """
        Rotates the slug used to address this dashboard publicly.
        """

        self.slug = Dashboard.create_new_slug()

    @staticmethod
    def create_new_slug() -> str:
        """
        Creates a new slug for a dashboard.

        :return: The new slug.
        """

        return secrets.token_urlsafe()

    @staticmethod
    def make_password(password: str) -> str:
        """
        Makes a password hash from the given password.

        :param password: The password to hash.
        :return: The hashed password.
        """

        return make_password(password)

    def set_password(self, password: str):
        """
        Sets the public dashboard password.

        :param password: The password to set.
        """

        self.public_password = Dashboard.make_password(password)

    def check_public_password(self, password: str) -> bool:
        """
        Checks if the given password matches the public dashboard password.

        :param password: The password to check.
        :return: True if the password matches, False otherwise.
        """

        if not self.public_has_password:
            return True
        return check_password(password, self.public_password)

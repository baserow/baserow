from baserow.contrib.automation.models import Automation
from baserow.contrib.builder.models import Builder
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.database.models import Database


class ApplicationFixtures:
    def create_database_application(self, user=None, **kwargs):
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        return Database.objects.create(**kwargs)

    def create_builder_application(self, user=None, **kwargs):
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        return Builder.objects.create(**kwargs)

    def create_dashboard_application(self, user=None, **kwargs):
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        return Dashboard.objects.create(**kwargs)

    def create_automation_application(self, user=None, **kwargs):
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        return Automation.objects.create(**kwargs)

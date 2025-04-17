from baserow.contrib.automation.models import AutomationWorkflow


class AutomationWorkflowFixtures:
    def create_automation_workflow(self, user=None, **kwargs):
        if not kwargs.get("automation", None):
            if user is None:
                user = self.create_user()

            kwargs["automation"] = self.create_automation_application(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = AutomationWorkflow.get_last_order(kwargs["automation"])

        return AutomationWorkflow.objects.create(**kwargs)

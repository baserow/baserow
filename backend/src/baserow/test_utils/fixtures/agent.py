from baserow.contrib.agent.models import AgentApplication


class AgentApplicationFixtures:
    def create_agent_application(self, user=None, **kwargs):
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=user)
        kwargs.setdefault("name", self.fake.name())
        kwargs.setdefault("order", 0)
        return AgentApplication.objects.create(**kwargs)

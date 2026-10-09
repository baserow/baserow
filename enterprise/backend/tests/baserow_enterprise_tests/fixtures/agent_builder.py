from baserow_enterprise.agent_builder.models import AgentBuilder, AgentDefinition


class AgentBuilderFixtures:
    def create_agent_builder_application(self, user=None, **kwargs):
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=user)
        kwargs.setdefault("name", self.fake.name())
        kwargs.setdefault("order", 0)
        return AgentBuilder.objects.create(**kwargs)

    def create_agent_definition(self, user=None, **kwargs):
        if "agent_builder" not in kwargs:
            kwargs["agent_builder"] = self.create_agent_builder_application(user=user)
        kwargs.setdefault("name", self.fake.name())
        kwargs.setdefault("order", 1)
        return AgentDefinition.objects.create(**kwargs)

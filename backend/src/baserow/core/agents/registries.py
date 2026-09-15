from baserow.core.registry import Instance, Registry


class AgentExtension(Instance):
    """Optional hooks for extending Agent API fields and persistence."""

    request_fields = {}
    response_fields = {}

    def enhance_queryset(self, queryset, workspace):
        return queryset

    def create(self, agent, values, user):
        pass

    def update(self, agent, values, user):
        pass

    def before_delete(self, agent, user):
        pass

    def role_uid_exists(self, role_uid, workspace):
        return None

    def get_default_role_uid(self, workspace):
        return None


class AgentExtensionRegistry(Registry[AgentExtension]):
    name = "agent_extension"

    def enhance_queryset(self, queryset, workspace):
        for extension in self.get_all():
            queryset = extension.enhance_queryset(queryset, workspace)
        return queryset

    def role_uid_exists(self, role_uid, workspace):
        answers = [
            extension.role_uid_exists(role_uid, workspace)
            for extension in self.get_all()
        ]
        answers = [answer for answer in answers if answer is not None]
        return any(answers) if answers else role_uid in {"ADMIN", "MEMBER"}

    def get_default_role_uid(self, workspace):
        for extension in self.get_all():
            role_uid = extension.get_default_role_uid(workspace)
            if role_uid is not None:
                return role_uid
        return "MEMBER"


agent_extension_registry = AgentExtensionRegistry()

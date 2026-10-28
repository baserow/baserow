from baserow.core.registry import Instance, Registry


class AgentExtensionType(Instance):
    """Optional hooks for extending Agent API fields and persistence."""

    request_fields = {}
    response_fields = {}
    # Fields `annotate_serialized_agents` adds to the agents of a list response,
    # declared for the API documentation only.
    list_response_fields = {}

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

    def annotate_serialized_agents(self, workspace, agents, serialized_agents, user):
        """
        Adds data to the serialized agents of a list response, for data that depends
        on the user requesting it and is cheaper to compute for a whole page at once.

        :param workspace: The workspace the agents are in.
        :param agents: The agents of the page.
        :param serialized_agents: The serialized agents, in the same order.
        :param user: The user requesting the list.
        :return: The serialized agents, annotated.
        """

        return serialized_agents


class AgentExtensionTypeRegistry(Registry[AgentExtensionType]):
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

    def annotate_serialized_agents(self, workspace, agents, serialized_agents, user):
        for extension in self.get_all():
            serialized_agents = extension.annotate_serialized_agents(
                workspace, agents, serialized_agents, user
            )
        return serialized_agents

    def get_default_role_uid(self, workspace):
        for extension in self.get_all():
            role_uid = extension.get_default_role_uid(workspace)
            if role_uid is not None:
                return role_uid
        return "MEMBER"


agent_extension_type_registry = AgentExtensionTypeRegistry()

from baserow.core.registry import Instance, Registry


class IdentityExtensionType(Instance):
    """Optional hooks for extending Identity API fields and persistence."""

    request_fields = {}
    response_fields = {}
    # Fields `annotate_serialized_identities` adds to the identities of a list response,
    # declared for the API documentation only.
    list_response_fields = {}

    def enhance_queryset(self, queryset, workspace):
        return queryset

    def create(self, identity, values, user):
        pass

    def update(self, identity, values, user):
        pass

    def before_delete(self, identity, user):
        pass

    def role_uid_exists(self, role_uid, workspace):
        return None

    def get_default_role_uid(self, workspace):
        return None

    def annotate_serialized_identities(
        self, workspace, identities, serialized_identities, user
    ):
        """
        Adds data to the serialized identities of a list response, for data that depends
        on the user requesting it and is cheaper to compute for a whole page at once.

        :param workspace: The workspace the identities are in.
        :param identities: The identities of the page.
        :param serialized_identities: The serialized identities, in the same order.
        :param user: The user requesting the list.
        :return: The serialized identities, annotated.
        """

        return serialized_identities


class IdentityExtensionTypeRegistry(Registry[IdentityExtensionType]):
    name = "identity_extension"

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

    def annotate_serialized_identities(
        self, workspace, identities, serialized_identities, user
    ):
        for extension in self.get_all():
            serialized_identities = extension.annotate_serialized_identities(
                workspace, identities, serialized_identities, user
            )
        return serialized_identities

    def get_default_role_uid(self, workspace):
        for extension in self.get_all():
            role_uid = extension.get_default_role_uid(workspace)
            if role_uid is not None:
                return role_uid
        return "MEMBER"


identity_extension_type_registry = IdentityExtensionTypeRegistry()

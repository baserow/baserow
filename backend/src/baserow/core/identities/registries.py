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

    def can_scope_to_applications(self, user, workspace) -> bool:
        """
        Whether the user can give a new identity of the workspace access to only
        some of its applications through this extension. Without one, an identity
        is a member of the whole workspace.

        :param user: The user who would create and scope the identity.
        :param workspace: The workspace of the identity.
        :return: True if `scope_to_applications` can be called for the user.
        """

        return False

    def scope_to_applications(self, identity, applications, user, roles):
        """
        Gives a new identity, which has no access by default, access to some of
        the given applications only. Only called when `can_scope_to_applications`
        is True. The identity must never get more than the user may change.

        :param identity: The identity to give access to.
        :param applications: The applications it may get a role on.
        :param user: The user who scopes the identity.
        :param roles: (application id, role uid) pairs: the role to give on each
            application. The uid is one `get_application_roles` returns, or the
            role an identity has on a workspace. The applications without a role
            that can be given on a single application get none.
        :raises IdentityCannotBeScoped: If the identity already has more access.
        """

        raise NotImplementedError()

    def get_application_roles(self, identity) -> list[tuple[int, str]] | None:
        """
        The roles an identity has on single applications, beside its role on the
        workspace, for an export to recreate them with `scope_to_applications`.

        :param identity: The identity whose roles are exported.
        :return: (application id, role uid) pairs, with the role that gives no
            access for an application whose roles can't be recreated this way, or
            None when the extension has no such roles.
        """

        return None

    def filter_readable_application_roles(self, roles: list, user, workspace) -> list:
        """
        Leaves out the applications whose roles the user may not read, so that an
        export doesn't tell them what an identity can reach there.

        :param roles: (application id, role uid) pairs.
        :param user: The user who would see them.
        :param workspace: The workspace of the applications.
        :return: The pairs the user may read.
        """

        return roles

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

    def get_application_scoper(self, user, workspace):
        """
        :return: The extension that can scope a new identity of the workspace to
            some applications for the user, or None.
        """

        return next(
            (
                extension
                for extension in self.get_all()
                if extension.can_scope_to_applications(user, workspace)
            ),
            None,
        )

    def get_application_roles(self, identity) -> list[tuple[int, str]] | None:
        """
        :return: The (application id, role uid) pairs an identity has beside its
            role on the workspace, or None when no extension has any.
        """

        for extension in self.get_all():
            roles = extension.get_application_roles(identity)
            if roles is not None:
                return roles
        return None

    def filter_readable_application_roles(self, roles: list, user, workspace) -> list:
        """:return: The (application id, role uid) pairs every extension lets the
        user read."""

        for extension in self.get_all():
            roles = extension.filter_readable_application_roles(roles, user, workspace)
        return roles

    def get_default_role_uid(self, workspace):
        for extension in self.get_all():
            role_uid = extension.get_default_role_uid(workspace)
            if role_uid is not None:
                return role_uid
        return "MEMBER"


identity_extension_type_registry = IdentityExtensionTypeRegistry()

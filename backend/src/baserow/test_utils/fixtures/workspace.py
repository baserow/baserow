from baserow.core.models import Workspace, WorkspaceInvitation, WorkspaceUser


class WorkspaceFixtures:
    def create_workspace(self, **kwargs):
        user = kwargs.pop("user", None)
        users = kwargs.pop("users", [])
        members = kwargs.pop("members", [])
        custom_permissions = kwargs.pop("custom_permissions", [])

        if user:
            users.insert(0, user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        workspace = Workspace.objects.create(**kwargs)

        for user in users:
            self.create_user_workspace(workspace=workspace, user=user, order=0)

        for user in members:
            self.create_user_workspace(
                workspace=workspace, user=user, permissions="MEMBER", order=0
            )

        for index, (user, permissions) in enumerate(custom_permissions):
            self.create_user_workspace(
                workspace=workspace, user=user, permissions=permissions, order=index
            )

        return workspace

    def create_user_workspace(self, **kwargs):
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace()

        if "user" not in kwargs:
            kwargs["user"] = self.create_user()

        if "order" not in kwargs:
            kwargs["order"] = 0

        if "permissions" not in kwargs:
            kwargs["permissions"] = "ADMIN"

        return WorkspaceUser.objects.create(**kwargs)

    def create_workspace_invitation(self, **kwargs):
        if "invited_by" not in kwargs:
            kwargs["invited_by"] = self.create_user()

        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=kwargs["invited_by"])

        if "email" not in kwargs:
            kwargs["email"] = self.fake.email()

        if "permissions" not in kwargs:
            kwargs["permissions"] = "ADMIN"

        if "message" not in kwargs:
            kwargs["message"] = self.fake.name()

        return WorkspaceInvitation.objects.create(**kwargs)

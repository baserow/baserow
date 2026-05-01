from baserow.contrib.automation.models import Automation
from baserow.contrib.builder.models import Builder
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.database.models import Database
from baserow.contrib.whiteboard.models import Whiteboard


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

    def create_whiteboard_application(self, user=None, **kwargs):
        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = 0

        return Whiteboard.objects.create(**kwargs)

    def create_whiteboard_comment(
        self,
        user=None,
        whiteboard=None,
        message=None,
        parent_comment=None,
        x=0.0,
        y=0.0,
        mentions=None,
        **kwargs,
    ):
        from baserow.contrib.whiteboard.comments.models import WhiteboardComment

        if whiteboard is None:
            whiteboard = self.create_whiteboard_application(user=user)
        if user is None:
            user = self.create_user()
        if message is None:
            message = {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": self.fake.sentence()}],
                    }
                ],
            }
        if parent_comment is not None:
            x = None
            y = None
        comment = WhiteboardComment.objects.create(
            whiteboard=whiteboard,
            user=user,
            message=message,
            parent_comment=parent_comment,
            x=x,
            y=y,
            **kwargs,
        )
        if mentions:
            comment.mentions.set(mentions)
        return comment

import secrets
from typing import List, Optional

from django.db.models import Max
from django.utils import timezone

from baserow.core.models import Template, TemplateCategory


class TemplateFixtures:
    def create_template_category(self, template=None, templates=None, **kwargs):
        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        category = TemplateCategory.objects.create(**kwargs)

        if not templates:
            templates = []

        if template:
            templates.append(template)

        category.templates.add(*templates)

        return category

    def create_template(self, category=None, categories=None, **kwargs):
        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "slug" not in kwargs:
            kwargs["slug"] = self.fake.unique.slug()

        if "icon" not in kwargs:
            kwargs["icon"] = "document"

        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace()

        if "type" not in kwargs:
            kwargs["type"] = Template.Type.OFFICIAL

        template = Template.objects.create(**kwargs)
        # Like the handlers, so that the cached template types of the workspace are
        # read again.
        template.workspace.save(update_fields=["updated_on"])

        if not categories:
            categories = []

        if category:
            categories.append(category)

        if len(categories) == 0:
            categories.append(self.create_template_category())

        template.categories.add(*categories)

        return template

    def create_user_template(self, user=None, **kwargs):
        if user is None:
            user = self.create_user()

        kwargs.setdefault("owner", user)
        kwargs.setdefault("author", user)

        return self.create_template(type=Template.Type.USER, **kwargs)

    def create_user_template_revision(self, root, **kwargs):
        if "version" not in kwargs:
            kwargs["version"] = (
                root.revisions.aggregate(version=Max("version"))["version"] or 1
            ) + 1

        return self.create_template(type=root.type, root=root, slug="", **kwargs)

    def set_user_template_state(
        self, template: Template, state: str, revision: Optional[Template] = None
    ) -> Template:
        """
        Puts a user template in `state`, like "public", "in_review" or
        "resubmitted" (in review again after a rejection). "shared" turns its
        private link on.

        :param template: The user template.
        :param state: The state to put it in.
        :param revision: The revision made public or reviewed, the template itself
            by default.
        :return: The template, refreshed.
        """

        revision = revision or template
        now = timezone.now()
        changes = {
            "private": {},
            "shared": {"private_link_token": secrets.token_hex(32)},
            "public": {"public_revision": revision},
            "blocked": {"blocked_at": now},
            "public_blocked": {"public_revision": revision, "blocked_at": now},
            "marked": {"marked_for_deletion_at": now},
            "in_review": {},
            "rejected": {},
            "resubmitted": {},
            "withdrawn_rejected": {},
        }[state]
        review = {
            "in_review": {
                "review_state": Template.ReviewState.PENDING,
                "submitted_on": now,
            },
            "rejected": {
                "review_state": Template.ReviewState.REJECTED,
                "reject_reason": "Reason",
                "submitted_on": now,
                "reviewed_on": now,
            },
            "resubmitted": {
                "review_state": Template.ReviewState.PENDING,
                "reject_reason": "Reason",
                "submitted_on": now,
                "reviewed_on": now,
            },
            "withdrawn_rejected": {
                "review_state": Template.ReviewState.WITHDRAWN,
                "reject_reason": "Reason",
            },
        }.get(state, {})
        if "public_revision" in changes:
            # Only an approved revision can be public, listed when it's reviewed.
            review = {"review_state": Template.ReviewState.APPROVED, "reviewed_on": now}
        if review:
            Template.objects.filter(id=revision.id).update(**review)
        Template.objects.filter(id=template.id).update(**changes)
        template.refresh_from_db()
        return template

    def set_user_template_revision_states(
        self, root: Template, states: List[str]
    ) -> Template:
        """
        Gives the user template a revision per state.

        :param root: The user template.
        :param states: The states of its revisions, oldest first.
        :return: The latest revision.
        """

        revision = root
        for index, state in enumerate(states):
            if state == "pruned":
                Template.objects.filter(id=revision.id).update(pruned_at=timezone.now())
                continue
            if index:
                revision = self.create_user_template_revision(root)
            self.set_user_template_state(root, state, revision)
        return revision

    def create_template_table(self, workspace, name="Content", row="Row"):
        """
        A database named `name` in the workspace of a template, with a table whose
        primary text field "Name" holds `row`.
        """

        database = self.create_database_application(workspace=workspace, name=name)
        table = self.create_database_table(database=database, name=f"{name} table")
        field = self.create_text_field(table=table, primary=True, name="Name")
        table.get_model().objects.create(**{field.db_column: row})
        return table

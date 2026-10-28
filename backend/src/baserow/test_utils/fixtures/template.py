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

    def set_user_template_state(self, template, state, revision=None):
        """
        Puts a user template in `state`: "private", "shared", "public", "blocked",
        "public_blocked" or "marked" for deletion. The shared or public revision
        is `revision`, the template itself by default.
        """

        revision = revision or template
        now = timezone.now()
        changes = {
            "private": {},
            "shared": {"shared_revision": revision},
            "public": {"public_revision": revision},
            "blocked": {"blocked_at": now},
            "public_blocked": {"public_revision": revision, "blocked_at": now},
            "marked": {"marked_for_deletion_at": now},
        }[state]
        if "public_revision" in changes:
            # Only an approved revision can be public.
            Template.objects.filter(id=revision.id).update(
                review_state=Template.ReviewState.APPROVED
            )
        Template.objects.filter(id=template.id).update(**changes)
        template.refresh_from_db()
        return template

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

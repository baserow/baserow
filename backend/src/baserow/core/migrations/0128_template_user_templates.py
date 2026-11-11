import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import baserow.core.models
from baserow.core.migration_utils import LockTimeoutMigration


def rename_duplicate_root_slugs(apps, schema_editor):
    """
    Appends the id to the slug of every root sharing its slug with an older root,
    and a counter on top if another root already uses the result.
    """

    Template = apps.get_model("core", "Template")
    roots = Template.objects.using(schema_editor.connection.alias).filter(
        root__isnull=True
    )
    max_length = Template._meta.get_field("slug").max_length

    taken = set()
    duplicates = []
    for template_id, slug in roots.order_by("id").values_list("id", "slug"):
        if slug in taken:
            duplicates.append((template_id, slug))
        else:
            taken.add(slug)

    for template_id, slug in duplicates:
        counter = 1
        suffix = f"-{template_id}"
        while (new_slug := slug[: max_length - len(suffix)] + suffix) in taken:
            counter += 1
            suffix = f"-{template_id}-{counter}"
        taken.add(new_slug)
        roots.filter(id=template_id).update(slug=new_slug)


class Migration(LockTimeoutMigration):
    """
    Changes `core_template` with a short lock timeout and retries, so that a long
    running transaction reading templates, like a template install, can't make
    every request touching templates wait behind the migration. Existing rows are
    backfilled in the next migration.
    """

    dependencies = [
        ("core", "0127_mcpendpoint_allowed_tools"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="settings",
            name="user_templates_require_approval",
            field=models.BooleanField(
                db_default=True,
                default=True,
                help_text="Indicates whether a user template must be approved by an admin before it's publicly listed.",
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="archive",
            field=models.FileField(
                blank=True,
                help_text="The downloadable file of this revision.",
                max_length=255,
                null=True,
                upload_to=baserow.core.models.template_archive_upload_to,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="author",
            field=models.ForeignKey(
                blank=True,
                help_text="The user who created a user template. Only set on user roots.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="authored_template_roots",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="blocked_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When an admin blocked the template. Only set on user roots.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="blocked_by",
            field=models.ForeignKey(
                blank=True,
                help_text="The admin who blocked the template.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="blocked_template_roots",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="blocked_reason",
            field=models.TextField(
                blank=True,
                db_default="",
                default="",
                help_text="Why the template was blocked, shown to its author.",
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="created_on",
            # Added without `auto_now_add` first, so existing rows stay null instead
            # of getting the time of the migration.
            field=models.DateTimeField(
                help_text="Null for templates created before this field existed.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="description",
            field=models.TextField(
                blank=True,
                db_default="",
                default="",
                help_text="The description of this revision.",
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="install_count",
            field=models.PositiveBigIntegerField(
                db_default=0,
                default=0,
                help_text="How many times any revision of the template was installed. Only counted on roots.",
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="marked_for_deletion_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the template was deleted. It's unavailable from then on and removed permanently later.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                help_text="The user who controls a user template. Only set on user roots.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="owned_template_roots",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="private_link_token",
            field=models.CharField(
                blank=True,
                help_text="The secret token of the private link. Null disables the link. Only set on user roots and never returned in ordinary responses.",
                max_length=64,
                null=True,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator("\\A[0-9a-f]{64}\\Z")
                ],
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="pruned_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the workspace and archive of this revision were removed to save space. The row itself is kept.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="public_revision",
            field=models.ForeignKey(
                blank=True,
                help_text="The approved revision that is publicly listed. Null means not listed. Only set on roots, pointing at the root or one of its revisions.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="published_by_roots",
                to="core.template",
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="reject_reason",
            field=models.TextField(
                blank=True,
                db_default="",
                default="",
                help_text="Why this revision was rejected, shown to the template author.",
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="review_state",
            field=models.CharField(
                choices=[
                    ("not_submitted", "Not submitted"),
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("withdrawn", "Withdrawn"),
                ],
                db_default="not_submitted",
                default="not_submitted",
                help_text="The review state of this revision. Approval alone doesn't list it, the root's `public_revision` does.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                help_text="The admin who last approved or rejected this revision.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_template_revisions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="reviewed_on",
            field=models.DateTimeField(
                blank=True,
                help_text="When this revision was last approved or rejected.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="root",
            field=models.ForeignKey(
                blank=True,
                help_text="The template this revision belongs to. Null for the template itself, which also holds revision 1.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="revisions",
                to="core.template",
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="shared_revision",
            field=models.ForeignKey(
                blank=True,
                help_text="The revision shared through the private link. Only set on roots, pointing at the root or one of its revisions.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="shared_by_roots",
                to="core.template",
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="submitted_on",
            field=models.DateTimeField(
                blank=True,
                help_text="When this revision was last submitted for review.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="type",
            field=models.CharField(
                choices=[("official", "Official"), ("user", "User")],
                help_text="Whether this is an official or a user template. Null means official. Revisions have the same type as their root.",
                max_length=16,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="updated_on",
            # Added without `auto_now` first, so existing rows stay null instead
            # of getting the time of the migration.
            field=models.DateTimeField(
                help_text="Null for templates not saved since this field existed.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="template",
            name="version",
            field=models.PositiveIntegerField(
                db_default=1,
                default=1,
                help_text="The revision number. 1 for the root, 2 or higher for later revisions.",
            ),
        ),
        migrations.AlterField(
            model_name="template",
            name="created_on",
            field=models.DateTimeField(
                auto_now_add=True,
                help_text="Null for templates created before this field existed.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="template",
            name="updated_on",
            field=models.DateTimeField(
                auto_now=True,
                help_text="Null for templates not saved since this field existed.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="template",
            name="slug",
            field=models.SlugField(
                blank=True,
                help_text="The permanent address of the template, unique among roots. For official templates it also matches the JSON file name. Empty for revisions.",
            ),
        ),
        migrations.AddIndex(
            model_name="template",
            index=models.Index(fields=["type"], name="core_template_type_idx"),
        ),
        migrations.AddIndex(
            model_name="template",
            index=models.Index(
                fields=["review_state", "submitted_on"], name="core_template_review_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("root__isnull", True), ("version", 1)),
                    models.Q(
                        ("author__isnull", True),
                        ("blocked_at__isnull", True),
                        ("blocked_by__isnull", True),
                        ("blocked_reason", ""),
                        ("install_count", 0),
                        ("marked_for_deletion_at__isnull", True),
                        ("owner__isnull", True),
                        ("private_link_token__isnull", True),
                        ("public_revision__isnull", True),
                        ("root__isnull", False),
                        ("shared_revision__isnull", True),
                        ("slug", ""),
                        ("version__gte", 2),
                    ),
                    _connector="OR",
                ),
                name="core_template_row_role",
            ),
        ),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("root__isnull", False),
                    models.Q(("slug", ""), _negated=True),
                    _connector="OR",
                ),
                name="core_template_root_slug",
            ),
        ),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.CheckConstraint(
                condition=models.Q(("type__in", ["official", "user"])),
                name="core_template_valid_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("type__isnull", False), ("type", "user")),
                    models.Q(("author__isnull", True), ("owner__isnull", True)),
                    _connector="OR",
                ),
                name="core_template_official_no_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("root__isnull", False),
                    ("type__isnull", True),
                    ("type", "official"),
                    ("owner__isnull", False),
                    ("marked_for_deletion_at__isnull", False),
                    _connector="OR",
                ),
                name="core_template_user_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("private_link_token__isnull", True),
                    models.Q(("private_link_token", ""), _negated=True),
                    _connector="OR",
                ),
                name="core_template_nonempty_token",
            ),
        ),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.UniqueConstraint(
                fields=("root", "version"), name="core_template_root_version"
            ),
        ),
        # Two syncs running at the same time could create two templates for the
        # same file. Keep the oldest slug and rename the others, so that the next
        # full sync removes them like any template without a file.
        migrations.RunPython(rename_duplicate_root_slugs, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.UniqueConstraint(
                condition=models.Q(("root__isnull", True)),
                fields=("slug",),
                name="core_template_unique_root_slug",
            ),
        ),
        migrations.AddConstraint(
            model_name="template",
            constraint=models.UniqueConstraint(
                condition=models.Q(("workspace__isnull", False)),
                fields=("workspace",),
                name="core_template_unique_workspace",
            ),
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("baserow_enterprise", "0077_row_comment_posted_trigger"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistantToolApproval",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("tool_call_id", models.CharField(max_length=255)),
                ("tool_name", models.CharField(max_length=100)),
                (
                    "tool_key",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="A digest of what the call changes when it was "
                        "held. An approved call only runs while it's the same.",
                        max_length=64,
                    ),
                ),
                (
                    "details",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="What the approval card shows: the changes the "
                        "call makes.",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("reason", models.TextField(blank=True, default="")),
                ("decided_on", models.DateTimeField(null=True)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "message",
                    models.ForeignKey(
                        help_text="The AI message whose run paused on the call.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approvals",
                        to="baserow_enterprise.assistantchatmessage",
                    ),
                ),
            ],
            options={
                "ordering": ("id",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("message", "tool_call_id"),
                        name="assistant_tool_approval_unique_call",
                    )
                ],
            },
        ),
    ]

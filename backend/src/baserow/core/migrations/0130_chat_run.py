import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0129_template_backfill_official"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("run_type", models.CharField(max_length=32)),
                ("chat_id", models.BigIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("context", models.JSONField(default=dict)),
                ("outcome", models.JSONField(null=True)),
                ("cancel_requested_at", models.DateTimeField(null=True)),
                ("lease_expires_at", models.DateTimeField(null=True)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("started_on", models.DateTimeField(null=True)),
                ("finished_on", models.DateTimeField(null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="core.workspace",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="chatrun",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ("queued", "running"))),
                fields=("run_type", "chat_id"),
                name="chat_run_one_active_per_chat",
            ),
        ),
        migrations.AddIndex(
            model_name="chatrun",
            index=models.Index(
                fields=["run_type", "chat_id", "-created_on"],
                name="chat_run_conversation_created",
            ),
        ),
        migrations.AddIndex(
            model_name="chatrun",
            index=models.Index(fields=["finished_on"], name="chat_run_finished"),
        ),
    ]

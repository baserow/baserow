from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0043_mcp_server_encrypted_secrets"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="httpformdata",
            options={"ordering": ("id",)},
        ),
        migrations.AlterModelOptions(
            name="httpheader",
            options={"ordering": ("id",)},
        ),
        migrations.AlterModelOptions(
            name="httpqueryparam",
            options={"ordering": ("id",)},
        ),
    ]

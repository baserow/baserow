from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0222_button_field_start_workflow_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="gridview",
            name="group_by_layout",
            field=models.CharField(
                choices=[("section", "Section"), ("column", "Column")],
                db_default="section",
                default="section",
                max_length=10,
                help_text="How grouped rows are presented: sections with a header above "
                "each group, or one column per group-by level beside the rows.",
            ),
        ),
    ]

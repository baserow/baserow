from baserow.core.formula.types import BaserowFormulaObject


def migrate_button_url_formulas_to_open_url_actions(apps, schema_editor):
    """
    Moves a button field's retired `url_formula` into the `open_url` action it
    is now expressed as. The attribute always opened a new tab, so the action
    keeps `blank` instead of taking the new `self` default.
    """

    ButtonField = apps.get_model("database", "ButtonField")
    OpenUrlWorkflowAction = apps.get_model("database", "OpenUrlWorkflowAction")
    ContentType = apps.get_model("contenttypes", "ContentType")

    # The content type row is normally created by the post-migrate signal,
    # which hasn't run yet while this migration is applying.
    content_type, _ = ContentType.objects.get_or_create(
        app_label="database", model="openurlworkflowaction"
    )

    for field in ButtonField.objects.all().iterator():
        url_formula = BaserowFormulaObject.to_formula(field.url_formula or "")
        if not url_formula.get("formula"):
            continue

        # Kept idempotent, so a re-run never stacks a second action on a field.
        if OpenUrlWorkflowAction.objects.filter(field_id=field.pk).exists():
            continue

        # Multi-table inheritance rules out `bulk_create`, so one row each.
        OpenUrlWorkflowAction.objects.create(
            content_type=content_type,
            field_id=field.pk,
            order=1,
            url=url_formula,
            target="blank",
        )

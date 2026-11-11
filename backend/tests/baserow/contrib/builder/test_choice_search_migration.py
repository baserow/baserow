import pytest


@pytest.mark.once_per_day_in_ci
def test_choice_search_migration_keeps_old_application_writes_compatible(migrator):
    old_state = migrator.migrate(
        [("builder", "0080_builderworkflowaction_trashed_and_more")]
    )
    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")
    Page = old_state.apps.get_model("builder", "Page")
    OldChoiceElement = old_state.apps.get_model("builder", "ChoiceElement")

    workspace = Workspace.objects.create(name="Workspace")
    builder = Builder.objects.create(
        order=1,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )
    page = Page.objects.create(order=1, builder=builder, name="Page", path="/page")
    choice_content_type = ContentType.objects.get_for_model(OldChoiceElement)
    existing_element = OldChoiceElement.objects.create(
        page=page, content_type=choice_content_type
    )

    new_state = migrator.migrate([("builder", "0081_choiceelement_show_search")])
    NewChoiceElement = new_state.apps.get_model("builder", "ChoiceElement")

    assert NewChoiceElement.objects.get(id=existing_element.id).show_search is False

    # The previous application version omits show_search in its INSERTs. The
    # database default must keep those writes valid during a rolling deployment.
    legacy_element = OldChoiceElement.objects.create(
        page=page, content_type=choice_content_type
    )
    assert NewChoiceElement.objects.get(id=legacy_element.id).show_search is False

    new_element = NewChoiceElement.objects.create(
        page_id=page.id, content_type_id=choice_content_type.id, show_search=True
    )
    legacy_element = OldChoiceElement.objects.get(id=new_element.id)
    legacy_element.show_as_dropdown = False
    legacy_element.save()
    new_element.refresh_from_db()
    assert new_element.show_search is True

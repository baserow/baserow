import random
import time

from django.db import connection

import pytest


@pytest.mark.once_per_day_in_ci
def test_0076_builder_breakpoints_preserves_existing_applications(
    migrator, teardown_table_metadata
):
    migrate_from = [("builder", "0075_container_element_positioning_behaviour")]
    migrate_to = [("builder", "0076_builder_breakpoints")]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")

    workspace = Workspace.objects.create(name="Workspace")
    builder = Builder.objects.create(
        order=1,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )

    new_state = migrator.migrate(migrate_to)
    Builder = new_state.apps.get_model("builder", "Builder")
    builder = Builder.objects.get(id=builder.id)

    assert builder.breakpoints == {"mobile": 500, "tablet": 768}


@pytest.mark.once_per_day_in_ci
def test_0010_remove_orphan_collection_fields_forwards(
    migrator, teardown_table_metadata
):
    migrate_from = [
        ("builder", "0009_element_visibility"),
    ]
    migrate_to = [
        ("builder", "0010_remove_orphan_collection_fields"),
    ]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")
    Page = old_state.apps.get_model("builder", "Page")
    TableElement = old_state.apps.get_model("builder", "TableElement")
    CollectionField = old_state.apps.get_model("builder", "CollectionField")

    workspace = Workspace.objects.create(name="Workspace")
    builder = Builder.objects.create(
        order=2,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )
    page = Page.objects.create(order=2, builder=builder, name="Page", path="page/")
    collection_field1 = CollectionField.objects.create(
        order=1, name="test1", type="text", config={}
    )
    # This orphan collection field should be deleted
    CollectionField.objects.create(order=1, name="test2", type="text", config={})
    table_element = TableElement.objects.create(
        order=1,
        page=page,
        items_per_page=5,
        content_type=ContentType.objects.get_for_model(TableElement),
    )
    table_element.fields.add(collection_field1)

    new_state = migrator.migrate(migrate_to)

    CollectionField = new_state.apps.get_model("builder", "CollectionField")

    assert CollectionField.objects.count() == 1
    assert CollectionField.objects.first().name == "test1"


@pytest.mark.once_per_day_in_ci
# You must add --run-once-per-day-in-ci to execute this test
def test_0018_resolve_collection_field_configs(migrator, teardown_table_metadata):
    migrate_from = [
        ("builder", "0017_repeatelement"),
    ]
    migrate_to = [
        ("builder", "0018_resolve_collection_field_configs"),
    ]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")
    Page = old_state.apps.get_model("builder", "Page")
    TableElement = old_state.apps.get_model("builder", "TableElement")
    CollectionField = old_state.apps.get_model("builder", "CollectionField")

    workspace = Workspace.objects.create(name="Workspace")
    builder = Builder.objects.create(
        order=2,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )
    page = Page.objects.create(order=2, builder=builder, name="Page", path="page/")

    field_without_target = CollectionField.objects.create(
        order=1,
        name="test1",
        type="link",
        config={
            "link_name": "My link",
            "navigate_to_page_id": 2,
            "navigate_to_url": "",
            "navigation_type": "page",
            "page_parameters": [],
        },
    )

    field_without_page_parameters = CollectionField.objects.create(
        order=2,
        name="test2",
        type="link",
        config={
            "link_name": "badger",
            "navigate_to_page_id": 2,
            "navigate_to_url": "",
            "navigation_type": "page",
            "target": "self",
        },
    )

    table_element = TableElement.objects.create(
        order=1,
        page=page,
        items_per_page=5,
        content_type=ContentType.objects.get_for_model(TableElement),
    )
    table_element.fields.add(field_without_target)
    table_element.fields.add(field_without_page_parameters)

    migrator.migrate(migrate_to)

    field_without_target.refresh_from_db()
    assert field_without_target.config["target"] == "self"

    field_without_page_parameters.refresh_from_db()
    assert field_without_page_parameters.config["page_parameters"] == []


@pytest.mark.once_per_day_in_ci
# You must add --run-once-per-day-in-ci to execute this test
def test_0025_theme_config_block(migrator, teardown_table_metadata):
    migrate_from = [
        ("builder", "0024_element_role_type_element_roles"),
    ]
    migrate_to = [
        ("builder", "0025_buttonthemeconfigblock_colorthemeconfigblock_and_more"),
    ]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")

    workspace = Workspace.objects.create(name="Workspace")
    builder = Builder.objects.create(
        order=2,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )

    builder.mainthemeconfigblock.primary_color = "#f00000ff"
    builder.mainthemeconfigblock.secondary_color = "#0eaa42ff"
    builder.mainthemeconfigblock.heading_1_font_size = "#0eaa42ff"
    builder.mainthemeconfigblock.heading_1_font_size = 30
    builder.mainthemeconfigblock.heading_1_color = "#ff0000ff"
    builder.mainthemeconfigblock.heading_2_font_size = 20
    builder.mainthemeconfigblock.heading_2_color = "#070810ff"
    builder.mainthemeconfigblock.heading_3_font_size = 16
    builder.mainthemeconfigblock.heading_3_color = "#070810ff"

    builder.mainthemeconfigblock.save()

    new_state = migrator.migrate(migrate_to)

    Builder = new_state.apps.get_model("builder", "Builder")
    builder = Builder.objects.get(id=builder.id)

    assert builder.colorthemeconfigblock.primary_color == "#f00000ff"
    assert builder.colorthemeconfigblock.secondary_color == "#0eaa42ff"
    assert builder.typographythemeconfigblock.heading_1_font_size == 30
    assert builder.typographythemeconfigblock.heading_1_text_color == "#ff0000ff"
    assert builder.typographythemeconfigblock.heading_2_font_size == 20
    assert builder.typographythemeconfigblock.heading_2_text_color == "#070810ff"
    assert builder.typographythemeconfigblock.heading_3_font_size == 16
    assert builder.typographythemeconfigblock.heading_3_text_color == "#070810ff"
    assert builder.buttonthemeconfigblock.button_background_color == "primary"


@pytest.mark.once_per_day_in_ci
# You must add --run-once-per-day-in-ci to execute this test
def test_0025_element_properties(migrator, teardown_table_metadata):
    migrate_from = [
        ("builder", "0024_element_role_type_element_roles"),
    ]
    migrate_to = [
        ("builder", "0025_buttonthemeconfigblock_colorthemeconfigblock_and_more"),
    ]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")
    Page = old_state.apps.get_model("builder", "Page")

    TableElement = old_state.apps.get_model("builder", "TableElement")
    HeadingElement = old_state.apps.get_model("builder", "HeadingElement")
    ButtonElement = old_state.apps.get_model("builder", "ButtonElement")
    LinkElement = old_state.apps.get_model("builder", "LinkElement")
    FormContainerElement = old_state.apps.get_model("builder", "FormContainerElement")

    workspace = Workspace.objects.create(name="Workspace")
    builder = Builder.objects.create(
        order=2,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )
    builder.mainthemeconfigblock.secondary_color = "#0eaa42ff"
    builder.mainthemeconfigblock.border_color = "#0eaa42ff"
    builder.mainthemeconfigblock.save()

    page = Page.objects.create(order=2, builder=builder, name="Page", path="page/")

    TableElement.objects.create(
        order=1,
        page=page,
        items_per_page=5,
        content_type=ContentType.objects.get_for_model(TableElement),
        button_color="#CCCCCCCC",
    )
    ButtonElement.objects.create(
        order=2,
        page=page,
        button_color="#CC00CCCC",
        content_type=ContentType.objects.get_for_model(ButtonElement),
    )
    ButtonElement.objects.create(
        order=3,
        page=page,
        button_color="secondary",
        content_type=ContentType.objects.get_for_model(ButtonElement),
    )
    ButtonElement.objects.create(
        order=4,
        page=page,
        button_color="border",
        content_type=ContentType.objects.get_for_model(ButtonElement),
    )
    ButtonElement.objects.create(
        order=5,
        page=page,
        button_color="blue",
        content_type=ContentType.objects.get_for_model(ButtonElement),
    )
    LinkElement.objects.create(
        order=2,
        page=page,
        button_color="#CCCC00CC",
        content_type=ContentType.objects.get_for_model(LinkElement),
    )
    FormContainerElement.objects.create(
        order=2,
        page=page,
        button_color="#CCCCCC00",
        content_type=ContentType.objects.get_for_model(FormContainerElement),
    )
    HeadingElement.objects.create(
        order=2,
        page=page,
        font_color="#0000CCCC",
        content_type=ContentType.objects.get_for_model(HeadingElement),
    )
    HeadingElement.objects.create(
        order=3,
        page=page,
        font_color="default",
        content_type=ContentType.objects.get_for_model(HeadingElement),
    )

    new_state = migrator.migrate(migrate_to)

    ButtonElement = new_state.apps.get_model("builder", "ButtonElement")
    HeadingElement = new_state.apps.get_model("builder", "HeadingElement")
    LinkElement = new_state.apps.get_model("builder", "LinkElement")
    FormContainerElement = new_state.apps.get_model("builder", "FormContainerElement")
    TableElement = new_state.apps.get_model("builder", "TableElement")

    [heading1, heading2] = HeadingElement.objects.filter(page__builder_id=builder.id)
    [button1, button2, button3, button4] = ButtonElement.objects.filter(
        page__builder_id=builder.id
    )
    link = LinkElement.objects.get(page__builder_id=builder.id)
    form = FormContainerElement.objects.get(page__builder_id=builder.id)
    table = TableElement.objects.get(page__builder_id=builder.id)

    assert table.styles == {
        "button": {
            "button_background_color": "#CCCCCCCC",
            "button_hover_background_color": "#dbdbdbcc",
        }
    }
    assert button1.styles == {
        "button": {
            "button_background_color": "#CC00CCCC",
            "button_hover_background_color": "#db4cdbcc",
        }
    }
    assert button2.styles == {
        "button": {
            "button_background_color": "secondary",
            "button_hover_background_color": "#56c37aff",
        }
    }
    assert button3.styles == {
        "button": {
            "button_background_color": "border",
            "button_hover_background_color": "#56c37aff",
        }
    }
    assert button4.styles == {
        "button": {
            "button_background_color": "blue",
            "button_hover_background_color": "blue",
        }
    }
    assert link.styles == {
        "button": {
            "button_background_color": "#CCCC00CC",
            "button_hover_background_color": "#dbdb4ccc",
        }
    }
    assert form.styles == {
        "button": {
            "button_background_color": "#CCCCCC00",
            "button_hover_background_color": "#dbdbdb00",
        }
    }
    assert heading1.styles == {
        "typography": {
            "heading_1_text_color": "#0000CCCC",
        }
    }
    assert heading2.styles == {}


@pytest.mark.once_per_day_in_ci
# You must add --run-once-per-day-in-ci to execute this test
def test_0026_element_styles(migrator, teardown_table_metadata):
    migrate_from = [
        ("builder", "0024_element_role_type_element_roles"),
    ]
    migrate_to = [
        ("builder", "0026_add_more_style_properties"),
    ]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")
    Page = old_state.apps.get_model("builder", "Page")

    ButtonElement = old_state.apps.get_model("builder", "ButtonElement")
    HeadingElement = old_state.apps.get_model("builder", "HeadingElement")
    LinkElement = old_state.apps.get_model("builder", "LinkElement")
    TextElement = old_state.apps.get_model("builder", "TextElement")
    ImageElement = old_state.apps.get_model("builder", "ImageElement")
    TableElement = old_state.apps.get_model("builder", "TableElement")
    FormContainerElement = old_state.apps.get_model("builder", "FormContainerElement")

    workspace = Workspace.objects.create(name="Workspace")
    builder = Builder.objects.create(
        order=2,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )
    page = Page.objects.create(order=2, builder=builder, name="Page", path="page/")
    builder.mainthemeconfigblock.secondary_color = "#0eaa42ff"
    builder.mainthemeconfigblock.border_color = "#0eaa42ff"
    builder.mainthemeconfigblock.save()

    HeadingElement.objects.create(
        order=2,
        page=page,
        alignment="center",
        content_type=ContentType.objects.get_for_model(HeadingElement),
    )
    ButtonElement.objects.create(
        order=2,
        page=page,
        alignment="right",
        content_type=ContentType.objects.get_for_model(ButtonElement),
    )
    ButtonElement.objects.create(
        order=3,
        page=page,
        button_color="#CCCCCCCC",
        alignment="right",
        content_type=ContentType.objects.get_for_model(ButtonElement),
    )
    ButtonElement.objects.create(
        order=4,
        page=page,
        button_color="secondary",
        content_type=ContentType.objects.get_for_model(ButtonElement),
    )
    ButtonElement.objects.create(
        order=5,
        page=page,
        button_color="blue",
        content_type=ContentType.objects.get_for_model(ButtonElement),
    )
    LinkElement.objects.create(
        order=2,
        page=page,
        button_color="#CCCC00CC",
        alignment="right",
        variant="button",
        content_type=ContentType.objects.get_for_model(LinkElement),
    )
    LinkElement.objects.create(
        order=3,
        page=page,
        button_color="#CCCC00CC",
        alignment="right",
        variant="link",
        content_type=ContentType.objects.get_for_model(LinkElement),
    )
    LinkElement.objects.create(
        order=4,
        page=page,
        button_color="border",
        content_type=ContentType.objects.get_for_model(LinkElement),
    )
    TextElement.objects.create(
        order=2,
        page=page,
        alignment="right",
        content_type=ContentType.objects.get_for_model(TextElement),
    )
    ImageElement.objects.create(
        order=2,
        page=page,
        style_image_constraint="full-width",
        alignment="center",
        style_max_width="50",
        style_max_height="50",
        content_type=ContentType.objects.get_for_model(ImageElement),
    )
    FormContainerElement.objects.create(
        order=2,
        page=page,
        content_type=ContentType.objects.get_for_model(FormContainerElement),
    )
    TableElement.objects.create(
        order=1,
        page=page,
        items_per_page=5,
        content_type=ContentType.objects.get_for_model(TableElement),
    )

    new_state = migrator.migrate(migrate_to)

    ButtonElement = new_state.apps.get_model("builder", "ButtonElement")
    HeadingElement = new_state.apps.get_model("builder", "HeadingElement")
    LinkElement = new_state.apps.get_model("builder", "LinkElement")
    TextElement = new_state.apps.get_model("builder", "TextElement")
    ImageElement = new_state.apps.get_model("builder", "ImageElement")
    TableElement = new_state.apps.get_model("builder", "TableElement")
    FormContainerElement = new_state.apps.get_model("builder", "FormContainerElement")

    heading = HeadingElement.objects.get(page__builder_id=builder.id)
    [button1, button2, button3, button4] = ButtonElement.objects.filter(
        page__builder_id=builder.id
    )
    [link1, link2, link3] = LinkElement.objects.filter(page__builder_id=builder.id)
    text = TextElement.objects.get(page__builder_id=builder.id)
    image = ImageElement.objects.get(page__builder_id=builder.id)
    form = FormContainerElement.objects.get(page__builder_id=builder.id)
    table = TableElement.objects.get(page__builder_id=builder.id)

    assert heading.styles == {
        "typography": {
            "heading_1_text_color": "default",
            "heading_1_text_alignment": "center",
        }
    }
    assert button1.styles == {"button": {"button_alignment": "right"}}
    assert button2.styles == {
        "button": {
            "button_alignment": "right",
            "button_background_color": "#CCCCCCCC",
            "button_hover_background_color": "#dbdbdbcc",
        }
    }
    assert button3.styles == {
        "button": {
            "button_background_color": "secondary",
            "button_hover_background_color": "#56c37aff",
        }
    }
    assert button4.styles == {
        "button": {
            "button_background_color": "blue",
            "button_hover_background_color": "blue",
        }
    }
    assert link1.styles == {
        "button": {
            "button_alignment": "right",
            "button_background_color": "#CCCC00CC",
            "button_hover_background_color": "#dbdb4ccc",
        }
    }
    assert link2.styles == {
        "link": {"link_text_alignment": "right"},
        "button": {
            "button_background_color": "#CCCC00CC",
            "button_hover_background_color": "#dbdb4ccc",
        },
    }
    assert link3.styles == {
        "button": {
            "button_background_color": "border",
            "button_hover_background_color": "#56c37aff",
        },
    }
    assert text.styles == {"typography": {"body_text_alignment": "right"}}
    assert image.styles == {
        "image": {
            "image_alignment": "center",
            "image_max_width": 50,
            "image_constraint": "full-width",
            "image_max_height": 50,
        }
    }
    assert form.styles == {"button": {"button_alignment": "right"}}
    assert table.styles == {"button": {"button_alignment": "center"}}


@pytest.mark.once_per_day_in_ci
# You must add --run-once-per-day-in-ci to execute this test
def test_0071_migrate_element_hierarchy_to_graph(migrator, teardown_table_metadata):
    migrate_from = [("builder", "0070_corecsvfilereaderworkflowaction")]
    migrate_to = [("builder", "0071_migrate_element_hierarchy_to_graph")]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")
    Page = old_state.apps.get_model("builder", "Page")

    HeaderElement = old_state.apps.get_model("builder", "HeaderElement")
    HeadingElement = old_state.apps.get_model("builder", "HeadingElement")
    ColumnElement = old_state.apps.get_model("builder", "ColumnElement")
    TextElement = old_state.apps.get_model("builder", "TextElement")

    workspace = Workspace.objects.create(name="Workspace")
    builder = Builder.objects.create(
        order=2,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )
    shared_page = Page.objects.create(
        order=1, builder=builder, name="__shared__", path="__shared__", shared=True
    )
    page = Page.objects.create(order=2, builder=builder, name="Page", path="")

    shared_header = HeaderElement.objects.create(
        page=page, content_type=ContentType.objects.get_for_model(HeaderElement)
    )
    shared_header.pages.add(*[page, shared_page])
    heading = HeadingElement.objects.create(
        order=1,
        page=page,
        parent_element=shared_header,
        value="'Welcome to my website'",
        content_type=ContentType.objects.get_for_model(HeadingElement),
    )

    column = ColumnElement.objects.create(
        order=2,
        page=page,
        column_amount=3,
        content_type=ContentType.objects.get_for_model(ColumnElement),
    )
    text_1_column_1 = TextElement.objects.create(
        order=1,
        page=page,
        parent_element=column,
        place_in_container="0",
        value="'Text 1 Column 1'",
        content_type=ContentType.objects.get_for_model(TextElement),
    )
    text_2_column_1 = TextElement.objects.create(
        order=2,
        page=page,
        parent_element=column,
        place_in_container="0",
        value="'Text 2 Column 1'",
        content_type=ContentType.objects.get_for_model(TextElement),
    )
    text_column_2 = TextElement.objects.create(
        order=1,
        page=page,
        parent_element=column,
        place_in_container="1",
        value="'Text Column 2'",
        content_type=ContentType.objects.get_for_model(TextElement),
    )
    text_column_3 = TextElement.objects.create(
        order=1,
        page=page,
        parent_element=column,
        place_in_container="2",
        value="'Text Column 3'",
        content_type=ContentType.objects.get_for_model(TextElement),
    )

    new_state = migrator.migrate(migrate_to)
    Page = new_state.apps.get_model("builder", "Page")

    migrated_page = Page.objects.get(pk=page.id)
    # Exact equality (not subset): a dropped/orphaned element would leave a key
    # missing from the real graph, which a subset assertion could not catch.
    assert migrated_page.graph == {
        "0": shared_header.id,
        str(shared_header.id): {
            "next": {"": [column.id]},
            "children": {"": [heading.id]},
        },
        str(heading.id): {},
        str(column.id): {
            "children": {
                "0": [text_1_column_1.id],
                "1": [text_column_2.id],
                "2": [text_column_3.id],
            }
        },
        str(text_1_column_1.id): {"next": {"": [text_2_column_1.id]}},
        str(text_2_column_1.id): {},
        str(text_column_2.id): {},
        str(text_column_3.id): {},
    }

    rollback_old_state = migrator.migrate(migrate_from)

    HeaderElement = rollback_old_state.apps.get_model("builder", "HeaderElement")
    HeadingElement = rollback_old_state.apps.get_model("builder", "HeadingElement")
    ColumnElement = rollback_old_state.apps.get_model("builder", "ColumnElement")
    TextElement = rollback_old_state.apps.get_model("builder", "TextElement")

    rollback_shared_header = HeaderElement.objects.get(pk=shared_header.id)
    rollback_heading = HeadingElement.objects.get(pk=heading.id)
    rollback_column = ColumnElement.objects.get(pk=column.id)
    rollback_text_1_column_1 = TextElement.objects.get(pk=text_1_column_1.id)
    rollback_text_2_column_1 = TextElement.objects.get(pk=text_2_column_1.id)
    rollback_text_column_2 = TextElement.objects.get(pk=text_column_2.id)
    rollback_text_column_3 = TextElement.objects.get(pk=text_column_3.id)

    assert rollback_shared_header.parent_element is None
    assert rollback_heading.parent_element_id == rollback_shared_header.id
    assert rollback_column.parent_element is None
    assert rollback_text_1_column_1.parent_element_id is rollback_column.id
    assert rollback_text_2_column_1.parent_element_id is rollback_column.id
    assert rollback_text_column_2.parent_element_id is rollback_column.id
    assert rollback_text_column_3.parent_element_id is rollback_column.id


@pytest.mark.once_per_day_in_ci
def test_0071_migrate_element_hierarchy_to_graph_performance(
    migrator, teardown_table_metadata
):
    migrate_from = [("builder", "0070_corecsvfilereaderworkflowaction")]
    migrate_to = [("builder", "0071_migrate_element_hierarchy_to_graph")]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Application = old_state.apps.get_model("core", "Application")
    Builder = old_state.apps.get_model("builder", "Builder")
    Page = old_state.apps.get_model("builder", "Page")
    # The migration reads builder_element only (not MTI sub-tables), so we only
    # need the base Element model. Skipping ColumnElement/TextElement sub-table
    # inserts halves the element write count without affecting migration output.
    Element = old_state.apps.get_model("builder", "element")

    builder_ct = ContentType.objects.get_for_model(Builder)
    column_ct = ContentType.objects.get_for_model(
        old_state.apps.get_model("builder", "ColumnElement")
    )
    text_ct = ContentType.objects.get_for_model(
        old_state.apps.get_model("builder", "TextElement")
    )

    # 2 sibling containers per page, each with 6 children = 14 elements per page.
    # This matches the production ratio of ~13.75 elements/page (209k elements / 152k pages).
    container_specs = [
        {"column_amount": 3, "places": [("0", 2), ("1", 2), ("2", 2)]},
        {"column_amount": 2, "places": [("0", 3), ("1", 3)]},
    ]

    # weights=[174, 776, 50] → mean 0.876 pages/workspace, matching production ratio
    # (152k pages / 174k workspaces). ~17% builders have 0 pages, ~78% have 1, ~5% have 2.
    rng = random.Random(0)
    num_workspaces = 17_359

    page_counts = [
        rng.choices([0, 1, 2], weights=[174, 776, 50])[0] for _ in range(num_workspaces)
    ]

    # Bulk create workspaces
    workspaces = Workspace.objects.bulk_create(
        [Workspace(name=f"Workspace {i}") for i in range(num_workspaces)]
    )

    # Bulk create Application rows (MTI parent of Builder)
    applications = Application.objects.bulk_create(
        [
            Application(
                order=1, name=f"Builder {i}", workspace=ws, content_type=builder_ct
            )
            for i, ws in enumerate(workspaces)
        ]
    )

    # Insert Builder rows directly — Django forbids bulk_create on MTI child models
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO builder_builder (application_ptr_id) VALUES (%s)",
            [(app.id,) for app in applications],
        )

    # Bulk create Pages
    page_records = []
    for app, count in zip(applications, page_counts):
        for j in range(count):
            page_records.append(
                Page(
                    order=j + 1,
                    builder_id=app.id,
                    name=f"Page {j}",
                    path=f"/{app.id}/{j}",
                )
            )
    pages = Page.objects.bulk_create(page_records)
    page_ids = [p.pk for p in pages]

    # Bulk create base Element rows for containers (one pass, preserving order so we
    # can index into col_elements by page_idx * n_specs + col_idx below)
    col_element_records = [
        Element(page=page, content_type=column_ct, order=col_order)
        for page in pages
        for col_order, _spec in enumerate(container_specs, start=1)
    ]
    col_elements = Element.objects.bulk_create(col_element_records)

    n_specs = len(container_specs)
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO builder_columnelement"
            " (element_ptr_id, column_amount, column_gap, alignment) VALUES (%s, %s, %s, %s)",
            [
                (
                    col_elements[i].id,
                    container_specs[i % n_specs]["column_amount"],
                    20,
                    "top",
                )
                for i in range(len(col_elements))
            ],
        )

    # Bulk create base Element rows for leaf text elements
    text_element_records = []
    for page_idx, page in enumerate(pages):
        for col_idx, spec in enumerate(container_specs):
            col_el = col_elements[page_idx * n_specs + col_idx]
            for place, count in spec["places"]:
                for order in range(1, count + 1):
                    text_element_records.append(
                        Element(
                            page=page,
                            content_type=text_ct,
                            order=order,
                            parent_element_id=col_el.id,
                            place_in_container=place,
                        )
                    )
    text_elements = Element.objects.bulk_create(text_element_records)

    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO builder_textelement (element_ptr_id, value, format) VALUES (%s, %s, %s)",
            [(e.id, "", "plain") for e in text_elements],
        )

    total_pages = len(page_ids)
    total_elements = total_pages * 14

    start = time.perf_counter()
    new_state = migrator.migrate(migrate_to)
    elapsed = time.perf_counter() - start

    print(f"\n[PERF] 0071_migrate_element_hierarchy_to_graph:")
    print(
        f"  {num_workspaces} workspaces · {total_pages} pages · {total_elements} elements"
    )
    print(f"  Total duration:    {elapsed:.3f}s")
    print(f"  Avg per page:      {elapsed / total_pages * 1000:.2f}ms")
    print(f"  Avg per workspace: {elapsed / num_workspaces * 1000:.2f}ms")

    Page = new_state.apps.get_model("builder", "Page")
    migrated = Page.objects.filter(pk__in=page_ids)
    assert all(p.graph for p in migrated), (
        "All pages must have a non-empty graph after migration"
    )

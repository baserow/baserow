from unittest.mock import Mock

import pytest
from udspy.module.callbacks import ModuleContext, is_module_callback

from baserow_enterprise.assistant.tools.builder.tools import get_theme_tool_factory
from baserow_enterprise.assistant.tools.builder.types.theme import (
    ButtonThemeUpdate,
    ColorThemeUpdate,
    ImageThemeUpdate,
    InputThemeUpdate,
    LinkThemeUpdate,
    PageThemeUpdate,
    TableThemeUpdate,
    TypographyThemeUpdate,
)

from .utils import fake_tool_helpers


def _get_theme_tools(user, workspace):
    """Helper to get the theme tools from the factory."""
    factory = get_theme_tool_factory(user, workspace, fake_tool_helpers)
    tools_upgrade = factory()

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))

    added_tools = mock_module.init_module.call_args[1]["tools"]
    get_theme = next((t for t in added_tools if t.name == "get_theme"), None)
    update_theme = next((t for t in added_tools if t.name == "update_theme"), None)
    return get_theme.func, update_theme.func


@pytest.mark.django_db
def test_theme_tool_factory_returns_callback(data_fixture):
    """Test that the theme tool factory returns a valid module callback."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    factory = get_theme_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)


@pytest.mark.django_db
def test_get_theme_returns_all_categories(data_fixture):
    """Test that get_theme returns all theme categories."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    get_theme, _ = _get_theme_tools(user, workspace)
    result = get_theme(application_id=builder.id)

    assert "theme" in result
    theme = result["theme"]

    # Verify all categories are present
    assert "colors" in theme
    assert "typography" in theme
    assert "buttons" in theme
    assert "links" in theme
    assert "images" in theme
    assert "page" in theme
    assert "inputs" in theme
    assert "tables" in theme


# =============================================================================
# Color Theme Tests
# =============================================================================


@pytest.mark.django_db
def test_update_theme_primary_color(data_fixture):
    """Test updating primary color."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    get_theme, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        colors=ColorThemeUpdate(primary_color="#ff5500ff"),
    )

    assert result["updated"] is True
    assert result["theme"]["colors"]["primary_color"] == "#ff5500ff"
    assert "warnings" not in result


@pytest.mark.django_db
def test_update_theme_all_colors(data_fixture):
    """Test updating all color properties."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        colors=ColorThemeUpdate(
            primary_color="#111111ff",
            secondary_color="#222222ff",
            border_color="#333333ff",
            main_success_color="#44ff44ff",
            main_warning_color="#ffff44ff",
            main_error_color="#ff4444ff",
        ),
    )

    assert result["updated"] is True
    colors = result["theme"]["colors"]
    assert colors["primary_color"] == "#111111ff"
    assert colors["secondary_color"] == "#222222ff"
    assert colors["border_color"] == "#333333ff"
    assert colors["main_success_color"] == "#44ff44ff"
    assert colors["main_warning_color"] == "#ffff44ff"
    assert colors["main_error_color"] == "#ff4444ff"


# =============================================================================
# Typography Theme Tests
# =============================================================================


@pytest.mark.django_db
def test_update_theme_body_typography(data_fixture):
    """Test updating body typography properties."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        typography=TypographyThemeUpdate(
            body_font_family="georgia",
            body_font_size=16,
            body_font_weight="medium",
            body_text_color="#333333ff",
            body_text_alignment="center",
        ),
    )

    assert result["updated"] is True
    body = result["theme"]["typography"]["body"]
    assert body["font_family"] == "georgia"
    assert body["font_size"] == 16
    assert body["font_weight"] == "medium"
    assert body["text_color"] == "#333333ff"
    assert body["text_alignment"] == "center"


@pytest.mark.django_db
def test_update_theme_heading_1(data_fixture):
    """Test updating heading 1 typography with flat keys."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        typography=TypographyThemeUpdate(
            heading_1_font_family="times_new_roman",
            heading_1_font_size=36,
            heading_1_font_weight="bold",
            heading_1_text_color="#2c3e50ff",
            heading_1_text_alignment="center",
        ),
    )

    assert result["updated"] is True
    headings = result["theme"]["typography"]["headings"]
    assert headings["heading_1_font_family"] == "times_new_roman"
    assert headings["heading_1_font_size"] == 36
    assert headings["heading_1_font_weight"] == "bold"
    assert headings["heading_1_text_color"] == "#2c3e50ff"
    assert headings["heading_1_text_alignment"] == "center"


@pytest.mark.django_db
def test_update_theme_heading_text_decoration(data_fixture):
    """Test updating heading text decoration as a list."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    # [underline, strike, uppercase, italic]
    result = update_theme(
        application_id=builder.id,
        typography=TypographyThemeUpdate(
            heading_1_text_decoration=[True, False, True, False],
        ),
    )

    assert result["updated"] is True
    headings = result["theme"]["typography"]["headings"]
    assert headings["heading_1_text_decoration"] == [True, False, True, False]


@pytest.mark.django_db
def test_update_theme_all_headings(data_fixture):
    """Test updating all heading levels."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        typography=TypographyThemeUpdate(
            heading_1_font_size=36,
            heading_2_font_size=28,
            heading_3_font_size=24,
            heading_4_font_size=20,
            heading_5_font_size=18,
            heading_6_font_size=16,
        ),
    )

    assert result["updated"] is True
    headings = result["theme"]["typography"]["headings"]
    assert headings["heading_1_font_size"] == 36
    assert headings["heading_2_font_size"] == 28
    assert headings["heading_3_font_size"] == 24
    assert headings["heading_4_font_size"] == 20
    assert headings["heading_5_font_size"] == 18
    assert headings["heading_6_font_size"] == 16


# =============================================================================
# Button Theme Tests
# =============================================================================


@pytest.mark.django_db
def test_update_theme_buttons(data_fixture):
    """Test updating button theme properties."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        buttons=ButtonThemeUpdate(
            font_family="arial",
            font_size=14,
            font_weight="semi_bold",
            background_color="#007bffff",
            text_color="#ffffffff",
            border_color="#0056b3ff",
            border_size=2,
            border_radius=8,
            vertical_padding=12,
            horizontal_padding=24,
        ),
    )

    assert result["updated"] is True
    buttons = result["theme"]["buttons"]
    assert buttons["font_family"] == "arial"
    assert buttons["font_size"] == 14
    assert buttons["font_weight"] == "semi_bold"
    assert buttons["background_color"] == "#007bffff"
    assert buttons["text_color"] == "#ffffffff"
    assert buttons["border_color"] == "#0056b3ff"
    assert buttons["border_size"] == 2
    assert buttons["border_radius"] == 8
    assert buttons["vertical_padding"] == 12
    assert buttons["horizontal_padding"] == 24


@pytest.mark.django_db
def test_update_theme_button_hover_states(data_fixture):
    """Test updating button hover and active states."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        buttons=ButtonThemeUpdate(
            hover_background_color="#0056b3ff",
            hover_text_color="#ffffffff",
            hover_border_color="#004085ff",
            active_background_color="#004085ff",
            active_text_color="#ffffffff",
            active_border_color="#002752ff",
        ),
    )

    assert result["updated"] is True
    buttons = result["theme"]["buttons"]
    assert buttons["hover_background_color"] == "#0056b3ff"
    assert buttons["hover_text_color"] == "#ffffffff"
    assert buttons["hover_border_color"] == "#004085ff"
    assert buttons["active_background_color"] == "#004085ff"
    assert buttons["active_text_color"] == "#ffffffff"
    assert buttons["active_border_color"] == "#002752ff"


# =============================================================================
# Link Theme Tests
# =============================================================================


@pytest.mark.django_db
def test_update_theme_links(data_fixture):
    """Test updating link theme properties."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        links=LinkThemeUpdate(
            font_family="verdana",
            font_size=14,
            font_weight="regular",
            text_color="#0066ccff",
            hover_text_color="#004499ff",
            active_text_color="#003366ff",
        ),
    )

    assert result["updated"] is True
    links = result["theme"]["links"]
    assert links["font_family"] == "verdana"
    assert links["font_size"] == 14
    assert links["font_weight"] == "regular"
    assert links["text_color"] == "#0066ccff"
    assert links["hover_text_color"] == "#004499ff"
    assert links["active_text_color"] == "#003366ff"


@pytest.mark.django_db
def test_update_theme_link_text_decorations(data_fixture):
    """Test updating link text decoration as lists."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        links=LinkThemeUpdate(
            default_text_decoration=[True, False, False, False],  # underline only
            hover_text_decoration=[True, False, False, False],
            active_text_decoration=[True, False, False, False],
        ),
    )

    assert result["updated"] is True
    links = result["theme"]["links"]
    assert links["default_text_decoration"] == [True, False, False, False]
    assert links["hover_text_decoration"] == [True, False, False, False]
    assert links["active_text_decoration"] == [True, False, False, False]


# =============================================================================
# Image Theme Tests
# =============================================================================


@pytest.mark.django_db
def test_update_theme_images(data_fixture):
    """Test updating image theme properties."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        images=ImageThemeUpdate(
            alignment="center",
            max_width=80,
            max_height=400,
            border_radius=8,
            constraint="contain",
        ),
    )

    assert result["updated"] is True
    images = result["theme"]["images"]
    assert images["alignment"] == "center"
    assert images["max_width"] == 80
    assert images["max_height"] == 400
    assert images["border_radius"] == 8
    assert images["constraint"] == "contain"


# =============================================================================
# Page Theme Tests
# =============================================================================


@pytest.mark.django_db
def test_update_theme_page_background(data_fixture):
    """Test updating page background properties."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        page=PageThemeUpdate(
            background_color="#f5f5f5ff",
            background_mode="fill",
        ),
    )

    assert result["updated"] is True
    page = result["theme"]["page"]
    assert page["background_color"] == "#f5f5f5ff"
    assert page["background_mode"] == "fill"


# =============================================================================
# Input Theme Tests
# =============================================================================


@pytest.mark.django_db
def test_update_theme_input_labels(data_fixture):
    """Test updating input label styling."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        inputs=InputThemeUpdate(
            label_font_family="arial",
            label_font_size=14,
            label_font_weight="medium",
            label_text_color="#333333ff",
        ),
    )

    assert result["updated"] is True
    label = result["theme"]["inputs"]["label"]
    assert label["font_family"] == "arial"
    assert label["font_size"] == 14
    assert label["font_weight"] == "medium"
    assert label["text_color"] == "#333333ff"


@pytest.mark.django_db
def test_update_theme_input_fields(data_fixture):
    """Test updating input field styling."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        inputs=InputThemeUpdate(
            input_font_family="inter",
            input_font_size=14,
            input_font_weight="regular",
            input_text_color="#333333ff",
            input_background_color="#ffffffff",
            input_border_color="#ccccccff",
            input_border_size=1,
            input_border_radius=4,
            input_vertical_padding=8,
            input_horizontal_padding=12,
        ),
    )

    assert result["updated"] is True
    inp = result["theme"]["inputs"]["input"]
    assert inp["font_family"] == "inter"
    assert inp["font_size"] == 14
    assert inp["font_weight"] == "regular"
    assert inp["text_color"] == "#333333ff"
    assert inp["background_color"] == "#ffffffff"
    assert inp["border_color"] == "#ccccccff"
    assert inp["border_size"] == 1
    assert inp["border_radius"] == 4
    assert inp["vertical_padding"] == 8
    assert inp["horizontal_padding"] == 12


# =============================================================================
# Table Theme Tests
# =============================================================================


@pytest.mark.django_db
def test_update_theme_table_border(data_fixture):
    """Test updating table border styling."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        tables=TableThemeUpdate(
            border_color="#ddddddff",
            border_size=1,
            border_radius=4,
        ),
    )

    assert result["updated"] is True
    border = result["theme"]["tables"]["border"]
    assert border["border_color"] == "#ddddddff"
    assert border["border_size"] == 1
    assert border["border_radius"] == 4


@pytest.mark.django_db
def test_update_theme_table_header(data_fixture):
    """Test updating table header styling."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        tables=TableThemeUpdate(
            header_background_color="#f0f0f0ff",
            header_text_color="#333333ff",
            header_font_family="arial",
            header_font_size=14,
            header_font_weight="bold",
            header_text_alignment="left",
        ),
    )

    assert result["updated"] is True
    header = result["theme"]["tables"]["header"]
    assert header["background_color"] == "#f0f0f0ff"
    assert header["text_color"] == "#333333ff"
    assert header["font_family"] == "arial"
    assert header["font_size"] == 14
    assert header["font_weight"] == "bold"
    assert header["text_alignment"] == "left"


@pytest.mark.django_db
def test_update_theme_table_cells(data_fixture):
    """Test updating table cell styling."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        tables=TableThemeUpdate(
            cell_background_color="#ffffffff",
            cell_alternate_background_color="#f9f9f9ff",
            cell_alignment="left",
            cell_vertical_padding=8,
            cell_horizontal_padding=12,
        ),
    )

    assert result["updated"] is True
    cell = result["theme"]["tables"]["cell"]
    assert cell["background_color"] == "#ffffffff"
    assert cell["alternate_background_color"] == "#f9f9f9ff"
    assert cell["alignment"] == "left"
    assert cell["vertical_padding"] == 8
    assert cell["horizontal_padding"] == 12


@pytest.mark.django_db
def test_update_theme_table_separators(data_fixture):
    """Test updating table separator styling."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        tables=TableThemeUpdate(
            vertical_separator_color="#e0e0e0ff",
            vertical_separator_size=1,
            horizontal_separator_color="#e0e0e0ff",
            horizontal_separator_size=1,
        ),
    )

    assert result["updated"] is True
    separator = result["theme"]["tables"]["separator"]
    assert separator["vertical_separator_color"] == "#e0e0e0ff"
    assert separator["vertical_separator_size"] == 1
    assert separator["horizontal_separator_color"] == "#e0e0e0ff"
    assert separator["horizontal_separator_size"] == 1


# =============================================================================
# Multiple Category Updates
# =============================================================================


@pytest.mark.django_db
def test_update_theme_multiple_categories(data_fixture):
    """Test updating multiple theme categories in a single call."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        colors=ColorThemeUpdate(primary_color="#ff0000ff"),
        typography=TypographyThemeUpdate(body_font_size=16),
        buttons=ButtonThemeUpdate(border_radius=8),
        page=PageThemeUpdate(background_color="#f0f0f0ff"),
    )

    assert result["updated"] is True
    assert result["theme"]["colors"]["primary_color"] == "#ff0000ff"
    assert result["theme"]["typography"]["body"]["font_size"] == 16
    assert result["theme"]["buttons"]["border_radius"] == 8
    assert result["theme"]["page"]["background_color"] == "#f0f0f0ff"


# =============================================================================
# Empty Update Tests
# =============================================================================


@pytest.mark.django_db
def test_update_theme_empty_returns_not_updated(data_fixture):
    """Test that empty update returns updated=False."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(application_id=builder.id)

    assert result["updated"] is False
    assert "theme" in result


# =============================================================================
# Verification Tests (warnings for mismatched values)
# =============================================================================


@pytest.mark.django_db
def test_update_theme_verifies_applied_properties(data_fixture):
    """Test that theme update verifies properties were applied correctly."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    # Valid update should have no warnings
    result = update_theme(
        application_id=builder.id,
        colors=ColorThemeUpdate(primary_color="#abcdefff"),
    )

    assert result["updated"] is True
    assert "warnings" not in result
    assert result["theme"]["colors"]["primary_color"] == "#abcdefff"


# =============================================================================
# Font Family Tests (all valid values)
# =============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "font_family",
    [
        "inter",
        "arial",
        "verdana",
        "tahoma",
        "trebuchet_ms",
        "times_new_roman",
        "georgia",
        "garamond",
        "courier_new",
        "brush_script_mt",
    ],
)
def test_update_theme_all_font_families(data_fixture, font_family):
    """Test that all font families can be set."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        typography=TypographyThemeUpdate(body_font_family=font_family),
    )

    assert result["updated"] is True
    assert result["theme"]["typography"]["body"]["font_family"] == font_family


# =============================================================================
# Font Weight Tests
# =============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "font_weight",
    ["regular", "medium", "semi_bold", "bold"],
)
def test_update_theme_all_font_weights(data_fixture, font_weight):
    """Test that all font weights can be set."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        typography=TypographyThemeUpdate(body_font_weight=font_weight),
    )

    assert result["updated"] is True
    assert result["theme"]["typography"]["body"]["font_weight"] == font_weight


# =============================================================================
# Alignment Tests
# =============================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "alignment",
    ["left", "center", "right"],
)
def test_update_theme_all_alignments(data_fixture, alignment):
    """Test that all alignments can be set."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)

    _, update_theme = _get_theme_tools(user, workspace)

    result = update_theme(
        application_id=builder.id,
        typography=TypographyThemeUpdate(body_text_alignment=alignment),
    )

    assert result["updated"] is True
    assert result["theme"]["typography"]["body"]["text_alignment"] == alignment

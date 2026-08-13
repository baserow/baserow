import pytest

from baserow.contrib.dashboard.widgets.grid_layout import (
    DASHBOARD_GRID_COLUMNS,
    compact_widget_layout,
    fits_within_grid_columns,
    get_first_available_grid_position,
    layouts_overlap,
)


def test_layouts_overlap_only_when_rectangles_share_area():
    layout = {
        "id": 1,
        "grid_x": 0,
        "grid_y": 0,
        "grid_width": 2,
        "grid_height": 4,
    }

    assert layouts_overlap(
        layout,
        {
            "id": 2,
            "grid_x": 1,
            "grid_y": 3,
            "grid_width": 2,
            "grid_height": 4,
        },
    )
    assert not layouts_overlap(
        layout,
        {
            "id": 2,
            "grid_x": 2,
            "grid_y": 0,
            "grid_width": 2,
            "grid_height": 4,
        },
    )
    assert not layouts_overlap(
        layout,
        {
            "id": 2,
            "grid_x": 0,
            "grid_y": 4,
            "grid_width": 2,
            "grid_height": 4,
        },
    )


@pytest.mark.parametrize(
    "layout, fits",
    [
        ({"grid_x": 0, "grid_width": DASHBOARD_GRID_COLUMNS}, True),
        ({"grid_x": 4, "grid_width": 2}, True),
        ({"grid_x": 5, "grid_width": 2}, False),
        ({"grid_x": -1, "grid_width": 1}, False),
        ({"grid_x": 0, "grid_width": 0}, False),
    ],
)
def test_fits_within_grid_columns(layout, fits):
    assert fits_within_grid_columns(layout) is fits


def test_compact_widget_layout_is_deterministic_and_does_not_mutate_inputs():
    layouts = [
        {
            "id": 1,
            "grid_x": 0,
            "grid_y": 8,
            "grid_width": 2,
            "grid_height": 4,
        },
        {
            "id": 2,
            "grid_x": 2,
            "grid_y": 4,
            "grid_width": 4,
            "grid_height": 4,
        },
        {
            "id": 3,
            "grid_x": 0,
            "grid_y": 0,
            "grid_width": 2,
            "grid_height": 4,
        },
    ]

    assert compact_widget_layout(layouts) == [
        {"id": 3, "grid_x": 0, "grid_y": 0, "grid_width": 2, "grid_height": 4},
        {"id": 2, "grid_x": 2, "grid_y": 0, "grid_width": 4, "grid_height": 4},
        {"id": 1, "grid_x": 0, "grid_y": 4, "grid_width": 2, "grid_height": 4},
    ]
    assert [layout["grid_y"] for layout in layouts] == [8, 4, 0]


def test_get_first_available_grid_position_fills_compatible_gaps():
    layouts = [
        {"id": 1, "grid_x": 0, "grid_y": 0, "grid_width": 2, "grid_height": 4},
        {"id": 2, "grid_x": 4, "grid_y": 0, "grid_width": 2, "grid_height": 4},
    ]

    assert get_first_available_grid_position(layouts, 2, 4) == (2, 0)


@pytest.mark.parametrize("grid_width, grid_height", [(0, 4), (7, 4), (2, 0)])
def test_get_first_available_grid_position_rejects_invalid_dimensions(
    grid_width, grid_height
):
    with pytest.raises(ValueError, match="dimensions"):
        get_first_available_grid_position([], grid_width, grid_height)

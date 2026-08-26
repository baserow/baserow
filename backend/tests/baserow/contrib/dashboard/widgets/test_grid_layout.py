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


def test_compact_widget_layout_fills_holes_across_overlapping_column_ranges():
    layouts = [
        {"id": 1, "grid_x": 0, "grid_y": 0, "grid_width": 3, "grid_height": 8},
        {"id": 2, "grid_x": 3, "grid_y": 0, "grid_width": 3, "grid_height": 4},
        {"id": 3, "grid_x": 3, "grid_y": 12, "grid_width": 3, "grid_height": 4},
        {"id": 4, "grid_x": 0, "grid_y": 20, "grid_width": 6, "grid_height": 4},
        {"id": 5, "grid_x": 0, "grid_y": 28, "grid_width": 3, "grid_height": 4},
    ]

    assert compact_widget_layout(layouts) == [
        {"id": 1, "grid_x": 0, "grid_y": 0, "grid_width": 3, "grid_height": 8},
        {"id": 2, "grid_x": 3, "grid_y": 0, "grid_width": 3, "grid_height": 4},
        {"id": 3, "grid_x": 3, "grid_y": 4, "grid_width": 3, "grid_height": 4},
        {"id": 4, "grid_x": 0, "grid_y": 8, "grid_width": 6, "grid_height": 4},
        {"id": 5, "grid_x": 0, "grid_y": 12, "grid_width": 3, "grid_height": 4},
    ]


def test_compact_widget_layout_treats_fixed_layouts_as_immutable_obstacles():
    fixed_layout = [
        {"id": 1, "grid_x": 0, "grid_y": 0, "grid_width": 2, "grid_height": 4}
    ]
    movable_layout = [
        {"id": 2, "grid_x": 0, "grid_y": 4, "grid_width": 2, "grid_height": 4},
        {"id": 3, "grid_x": 2, "grid_y": 4, "grid_width": 2, "grid_height": 4},
    ]

    assert compact_widget_layout(movable_layout, fixed_layouts=fixed_layout) == [
        {"id": 2, "grid_x": 0, "grid_y": 4, "grid_width": 2, "grid_height": 4},
        {"id": 3, "grid_x": 2, "grid_y": 0, "grid_width": 2, "grid_height": 4},
    ]


def test_compact_widget_layout_handles_a_large_stack():
    layouts = [
        {
            "id": index,
            "grid_x": 0,
            "grid_y": index * 12,
            "grid_width": DASHBOARD_GRID_COLUMNS,
            "grid_height": 4,
        }
        for index in range(800)
    ]

    compacted = compact_widget_layout(layouts)

    assert len(compacted) == 800
    assert [layout["grid_y"] for layout in compacted] == [
        index * 4 for index in range(800)
    ]


def test_get_first_available_grid_position_fills_compatible_gaps():
    layouts = [
        {"id": 1, "grid_x": 0, "grid_y": 0, "grid_width": 2, "grid_height": 4},
        {"id": 2, "grid_x": 4, "grid_y": 0, "grid_width": 2, "grid_height": 4},
    ]

    assert get_first_available_grid_position(layouts, 2, 4) == (2, 0)


def test_get_first_available_grid_position_skips_to_collision_bottom_edges():
    layouts = [
        {
            "id": 1,
            "grid_x": 0,
            "grid_y": 0,
            "grid_width": DASHBOARD_GRID_COLUMNS,
            "grid_height": 1_000_000_000,
        },
        {
            "id": 2,
            "grid_x": 0,
            "grid_y": 1_000_000_000,
            "grid_width": DASHBOARD_GRID_COLUMNS,
            "grid_height": 4,
        },
    ]

    assert get_first_available_grid_position(layouts, 2, 4) == (0, 1_000_000_004)


@pytest.mark.parametrize("grid_width, grid_height", [(0, 4), (7, 4), (2, 0)])
def test_get_first_available_grid_position_rejects_invalid_dimensions(
    grid_width, grid_height
):
    with pytest.raises(ValueError, match="dimensions"):
        get_first_available_grid_position([], grid_width, grid_height)

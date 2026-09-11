"""Pure helpers for the canonical dashboard widget grid."""

from collections.abc import Iterable, Mapping
from itertools import chain

DASHBOARD_GRID_COLUMNS = 6


def layouts_overlap(first: Mapping[str, int], second: Mapping[str, int]) -> bool:
    """Returns whether two rectangular widget layouts overlap."""

    return (
        first["grid_x"] < second["grid_x"] + second["grid_width"]
        and second["grid_x"] < first["grid_x"] + first["grid_width"]
        and first["grid_y"] < second["grid_y"] + second["grid_height"]
        and second["grid_y"] < first["grid_y"] + first["grid_height"]
    )


def fits_within_grid_columns(layout: Mapping[str, int]) -> bool:
    """Returns whether a layout fits horizontally in the canonical grid."""

    return (
        layout["grid_x"] >= 0
        and 1 <= layout["grid_width"] <= DASHBOARD_GRID_COLUMNS
        and layout["grid_x"] + layout["grid_width"] <= DASHBOARD_GRID_COLUMNS
    )


def horizontal_ranges_overlap(
    first: Mapping[str, int], second: Mapping[str, int]
) -> bool:
    """Returns whether two widget layouts share at least one grid column."""

    return (
        first["grid_x"] < second["grid_x"] + second["grid_width"]
        and second["grid_x"] < first["grid_x"] + first["grid_width"]
    )


def get_non_overlapping_grid_y(
    layout: Mapping[str, int], obstacles: Iterable[Mapping[str, int]]
) -> int:
    """Finds the first free row at or below the requested position.

    Jump to obstacle edges instead of visiting each row, so even large gaps have
    a cost bounded by the number of widgets rather than their coordinates.
    """

    grid_y = layout["grid_y"]
    occupied_intervals = sorted(
        (other["grid_y"], other["grid_y"] + other["grid_height"])
        for other in obstacles
        if horizontal_ranges_overlap(layout, other)
    )
    for start, end in occupied_intervals:
        if end <= grid_y:
            continue
        if start >= grid_y + layout["grid_height"]:
            break
        grid_y = end
    return grid_y


def compact_widget_layout(
    layouts: Iterable[Mapping[str, int]],
    fixed_layouts: Iterable[Mapping[str, int]] = (),
) -> list[dict[str, int]]:
    """Vertically compacts layouts without crossing widgets in overlapping columns.

    Layouts are processed top-to-bottom, then left-to-right, to make the result
    deterministic independently from the browser grid implementation. Fixed layouts
    are immutable obstacles: they affect where movable layouts settle but are not
    included in the result.
    """

    fixed_layout = list(fixed_layouts)
    compacted_layout: list[dict[str, int]] = []
    for source_layout in sorted(
        layouts,
        key=lambda layout: (layout["grid_y"], layout["grid_x"], layout["id"]),
    ):
        layout = dict(source_layout)
        preceding_layouts = chain(
            compacted_layout,
            (other for other in fixed_layout if other["grid_y"] < layout["grid_y"]),
        )
        layout["grid_y"] = max(
            (
                other["grid_y"] + other["grid_height"]
                for other in preceding_layouts
                if horizontal_ranges_overlap(layout, other)
            ),
            default=0,
        )
        layout["grid_y"] = get_non_overlapping_grid_y(
            layout, chain(fixed_layout, compacted_layout)
        )

        compacted_layout.append(layout)

    return compacted_layout


def resolve_widget_layout_collisions(
    layouts: Iterable[Mapping[str, int]],
    fixed_layouts: Iterable[Mapping[str, int]],
) -> list[dict[str, int]]:
    """Moves recorded layouts down only when their old positions are occupied.

    Widgets outside the recorded action are fixed obstacles. Preserve each saved
    position where possible, including gaps, so undo does not compact newer edits.
    """

    occupied = list(fixed_layouts)
    resolved = []
    for source in sorted(
        layouts, key=lambda item: (item["grid_y"], item["grid_x"], item["id"])
    ):
        item = dict(source)
        item["grid_y"] = get_non_overlapping_grid_y(item, occupied)
        occupied.append(item)
        resolved.append(item)
    return resolved


def get_first_available_grid_position(
    layouts: Iterable[Mapping[str, int]],
    grid_width: int,
    grid_height: int,
) -> tuple[int, int]:
    """Returns the first row-major position where a widget can fit."""

    if not 1 <= grid_width <= DASHBOARD_GRID_COLUMNS or grid_height < 1:
        raise ValueError("The widget dimensions do not fit in the dashboard grid.")

    layout = list(layouts)
    available_positions = []
    for grid_x in range(DASHBOARD_GRID_COLUMNS - grid_width + 1):
        candidate = {
            "grid_x": grid_x,
            "grid_y": 0,
            "grid_width": grid_width,
            "grid_height": grid_height,
        }
        grid_y = get_non_overlapping_grid_y(candidate, layout)
        available_positions.append((grid_y, grid_x))

    grid_y, grid_x = min(available_positions)
    return grid_x, grid_y

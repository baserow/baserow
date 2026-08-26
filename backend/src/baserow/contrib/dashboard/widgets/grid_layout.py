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


def compact_widget_layout(
    layouts: Iterable[Mapping[str, int]],
    fixed_layouts: Iterable[Mapping[str, int]] = (),
) -> list[dict[str, int]]:
    """Vertically compacts layouts while preserving their horizontal geometry.

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
        grid_y = 0
        occupied_intervals = sorted(
            (
                other["grid_y"],
                other["grid_y"] + other["grid_height"],
            )
            for other in chain(fixed_layout, compacted_layout)
            if horizontal_ranges_overlap(layout, other)
        )
        for interval_start, interval_end in occupied_intervals:
            if interval_end <= grid_y:
                continue
            if interval_start >= grid_y + layout["grid_height"]:
                break
            grid_y = max(grid_y, interval_end)

        layout["grid_y"] = grid_y

        compacted_layout.append(layout)

    return compacted_layout


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
        grid_y = 0
        while True:
            candidate = {
                "grid_x": grid_x,
                "grid_y": grid_y,
                "grid_width": grid_width,
                "grid_height": grid_height,
            }
            collisions = [
                existing for existing in layout if layouts_overlap(candidate, existing)
            ]
            if not collisions:
                available_positions.append((grid_y, grid_x))
                break

            # At least one of the current collisions remains until the greatest
            # bottom edge, so no position before it can fit at this grid_x.
            grid_y = max(
                existing["grid_y"] + existing["grid_height"] for existing in collisions
            )

    grid_y, grid_x = min(available_positions)
    return grid_x, grid_y

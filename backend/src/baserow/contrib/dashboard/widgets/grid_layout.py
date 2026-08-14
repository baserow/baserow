"""Pure helpers for the canonical dashboard widget grid."""

from collections.abc import Iterable, Mapping

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


def compact_widget_layout(
    layouts: Iterable[Mapping[str, int]],
) -> list[dict[str, int]]:
    """Vertically compacts layouts while preserving their horizontal geometry.

    Layouts are processed top-to-bottom, then left-to-right, to make the result
    deterministic independently from the browser grid implementation.
    """

    compacted_layout: list[dict[str, int]] = []
    for source_layout in sorted(
        layouts,
        key=lambda layout: (layout["grid_y"], layout["grid_x"], layout["id"]),
    ):
        layout = dict(source_layout)
        layout["grid_y"] = 0

        while any(layouts_overlap(layout, other) for other in compacted_layout):
            layout["grid_y"] += 1

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

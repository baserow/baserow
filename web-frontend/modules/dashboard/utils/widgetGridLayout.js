export const DASHBOARD_GRID_COLUMNS = 6

const FALLBACK_GRID_LAYOUT = {
  min_width: 1,
  min_height: 1,
  max_width: DASHBOARD_GRID_COLUMNS,
  max_height: 16,
}

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)

const asGridNumber = (value, fallback) =>
  Number.isInteger(value) ? value : fallback

export function sortWidgetsByGridPosition(widgets) {
  return [...widgets].sort((first, second) => {
    const byY = asGridNumber(first.grid_y, 0) - asGridNumber(second.grid_y, 0)
    if (byY !== 0) {
      return byY
    }

    const byX = asGridNumber(first.grid_x, 0) - asGridNumber(second.grid_x, 0)
    if (byX !== 0) {
      return byX
    }

    return first.id - second.id
  })
}

function getCanonicalLayoutItem(widget) {
  const width = clamp(
    asGridNumber(widget.grid_width, DASHBOARD_GRID_COLUMNS),
    1,
    DASHBOARD_GRID_COLUMNS
  )
  const savedX = asGridNumber(widget.grid_x, 0)
  const wrappedX =
    ((savedX % DASHBOARD_GRID_COLUMNS) + DASHBOARD_GRID_COLUMNS) %
    DASHBOARD_GRID_COLUMNS

  return {
    i: widget.id,
    x: clamp(wrappedX, 0, DASHBOARD_GRID_COLUMNS - width),
    y: asGridNumber(widget.grid_y, 0),
    w: width,
    h: Math.max(1, asGridNumber(widget.grid_height, 9)),
  }
}

function collides(first, second) {
  return (
    first.x < second.x + second.w &&
    second.x < first.x + first.w &&
    first.y < second.y + second.h &&
    second.y < first.y + first.h
  )
}

function firstAvailableRow(layout, item, minimumY = 0) {
  const candidate = { ...item, y: minimumY }

  let collisions = layout.filter((other) => collides(candidate, other))
  while (collisions.length > 0) {
    candidate.y = Math.max(...collisions.map((other) => other.y + other.h))
    collisions = layout.filter((other) => collides(candidate, other))
  }

  return candidate.y
}

/**
 * Plans a resize from the saved layout so reversing the gesture also restores
 * neighbors. Width growth pushes right first; height growth pushes downward.
 */
export function resizeWidgetGridLayout(layout, widgetId, width, height) {
  const original = layout.find((item) => String(item.i) === String(widgetId))
  const resized = { ...original, w: width, h: height }
  const occupied = [resized]
  const resolved = []
  const neighbors = layout
    .filter((item) => item !== original)
    .toSorted(
      (first, second) =>
        first.y - second.y ||
        first.x - second.x ||
        Number(first.i) - Number(second.i)
    )

  for (const source of neighbors) {
    let item = { ...source }
    if (width > original.w) {
      for (let x = item.x; x <= DASHBOARD_GRID_COLUMNS - item.w; x++) {
        const candidate = { ...item, x }
        if (!occupied.some((other) => collides(candidate, other))) {
          item = candidate
          break
        }
      }
    }
    const minimumY = resolved.reduce((y, other) => {
      return item.x < other.x + other.w && other.x < item.x + item.w
        ? Math.max(y, other.y + other.h)
        : y
    }, item.y)
    item.y = firstAvailableRow(occupied, item, minimumY)
    occupied.push(item)
    resolved.push(item)
  }

  const byId = new Map(occupied.map((item) => [String(item.i), item]))
  return layout.map((item) => byId.get(String(item.i)))
}

/**
 * Uses saved six-column coordinates at every viewport size and in both modes.
 */
export function createWidgetGridLayout(widgets) {
  return sortWidgetsByGridPosition(widgets).reduce((layout, widget) => {
    const item = getCanonicalLayoutItem(widget)
    item.y = firstAvailableRow(layout, item, item.y)
    layout.push(item)
    return layout
  }, [])
}

export function getWidgetGridItemConstraints(widget, layoutItem) {
  const constraints = widget?.grid_layout || FALLBACK_GRID_LAYOUT
  const maxW = Math.min(
    DASHBOARD_GRID_COLUMNS,
    asGridNumber(constraints.max_width, DASHBOARD_GRID_COLUMNS)
  )
  const maxH = asGridNumber(constraints.max_height, 16)

  return {
    minW: Math.min(
      maxW,
      layoutItem.w,
      Math.max(1, asGridNumber(constraints.min_width, 1))
    ),
    minH: Math.min(
      maxH,
      layoutItem.h,
      Math.max(1, asGridNumber(constraints.min_height, 1))
    ),
    maxW,
    maxH,
  }
}

export function toWidgetLayoutPayload(layout) {
  return layout.map((item) => ({
    id: Number(item.i),
    grid_x: item.x,
    grid_y: item.y,
    grid_width: item.w,
    grid_height: item.h,
  }))
}

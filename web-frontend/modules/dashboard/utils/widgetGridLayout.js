export const DASHBOARD_DESKTOP_GRID_COLUMNS = 6
export const DASHBOARD_TABLET_GRID_COLUMNS = 4
export const DASHBOARD_MOBILE_GRID_COLUMNS = 1

const DESKTOP_BREAKPOINT = 920
const TABLET_BREAKPOINT = 600

const FALLBACK_GRID_LAYOUT = {
  min_width: 1,
  min_height: 1,
  max_width: DASHBOARD_DESKTOP_GRID_COLUMNS,
  max_height: 16,
}

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)

const asGridNumber = (value, fallback) =>
  Number.isInteger(value) ? value : fallback

export function getDashboardGridColumns(availableWidth) {
  if (availableWidth >= DESKTOP_BREAKPOINT) {
    return DASHBOARD_DESKTOP_GRID_COLUMNS
  }
  if (availableWidth >= TABLET_BREAKPOINT) {
    return DASHBOARD_TABLET_GRID_COLUMNS
  }
  return DASHBOARD_MOBILE_GRID_COLUMNS
}

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
  return {
    i: widget.id,
    x: asGridNumber(widget.grid_x, 0),
    y: asGridNumber(widget.grid_y, 0),
    w: clamp(
      asGridNumber(widget.grid_width, DASHBOARD_DESKTOP_GRID_COLUMNS),
      1,
      DASHBOARD_DESKTOP_GRID_COLUMNS
    ),
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
      for (let x = item.x; x <= DASHBOARD_DESKTOP_GRID_COLUMNS - item.w; x++) {
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

function projectLayoutItem(item, columns) {
  if (columns === DASHBOARD_DESKTOP_GRID_COLUMNS) {
    return { ...item }
  }

  if (columns === DASHBOARD_MOBILE_GRID_COLUMNS) {
    return { ...item, x: 0, w: 1 }
  }

  const scale = columns / DASHBOARD_DESKTOP_GRID_COLUMNS
  const width = clamp(Math.round(item.w * scale), 1, columns)
  const x = clamp(Math.round(item.x * scale), 0, columns - width)

  return { ...item, x, w: width }
}

/**
 * Returns a visual layout for the available container width. Only the six-column
 * layout is persisted; tablet and mobile positions are deterministic projections.
 */
export function createWidgetGridLayout(
  widgets,
  columns = DASHBOARD_DESKTOP_GRID_COLUMNS
) {
  const canonicalLayout = sortWidgetsByGridPosition(widgets).map(
    getCanonicalLayoutItem
  )

  if (columns === DASHBOARD_DESKTOP_GRID_COLUMNS) {
    return canonicalLayout
  }

  return canonicalLayout.reduce((projectedLayout, item) => {
    const projectedItem = projectLayoutItem(item, columns)
    projectedItem.y = firstAvailableRow(projectedLayout, projectedItem)
    projectedLayout.push(projectedItem)
    return projectedLayout
  }, [])
}

export function getWidgetGridItemConstraints(widget, columns, layoutItem) {
  const constraints = widget?.grid_layout || FALLBACK_GRID_LAYOUT
  const maxW = Math.min(
    columns,
    asGridNumber(constraints.max_width, DASHBOARD_DESKTOP_GRID_COLUMNS)
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

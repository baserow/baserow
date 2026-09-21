/**
 * Returns the widths to use when rendering group-by columns in the available space.
 * The configured widths are left untouched so they can be restored exactly when the
 * viewport grows again. If the columns need to shrink, only the space above the
 * minimum width is scaled, which also preserves columns explicitly set to the
 * minimum.
 */
export function fitGroupByWidths(groupBys, availableWidth, minimumWidth) {
  const widths = groupBys.map((groupBy) =>
    Math.max(groupBy.width, minimumWidth)
  )
  const totalWidth = widths.reduce((total, width) => total + width, 0)

  if (
    availableWidth === null ||
    availableWidth === undefined ||
    totalWidth <= availableWidth
  ) {
    return widths
  }

  const minimumTotalWidth = minimumWidth * widths.length
  if (availableWidth <= minimumTotalWidth) {
    return widths.map(() => minimumWidth)
  }

  const flexibleWidth = totalWidth - minimumTotalWidth
  const availableFlexibleWidth = availableWidth - minimumTotalWidth
  const scale = availableFlexibleWidth / flexibleWidth

  return widths.map((width) => minimumWidth + (width - minimumWidth) * scale)
}

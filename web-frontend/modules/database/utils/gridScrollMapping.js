// Firefox cannot render elements taller than ~17.9 million CSS pixels;
// beyond that threshold the scrollbar collapses. 10 million is a
// conservative cap that stays well within every browser's limit.
export const MAX_SAFE_SCROLL_HEIGHT = 10_000_000

/**
 * Converts a real DOM scrollTop to a virtual scrollTop using fraction-based
 * mapping. When the placeholder height is capped below the true virtual
 * height, this maps the compressed scroll range to the full virtual range.
 */
export function realToVirtualScrollTop(
  scrollTop,
  placeholderHeight,
  virtualHeight,
  windowHeight
) {
  const maxRealScroll = Math.max(placeholderHeight - windowHeight, 1)
  const maxVirtualScroll = Math.max(virtualHeight - windowHeight, 0)
  const scrollFraction = Math.min(scrollTop / maxRealScroll, 1)
  return scrollFraction * maxVirtualScroll
}

/**
 * Computes the middle row index visible in the scroll window. This is the
 * central building block for both fetch and visibility calculations.
 */
export function getMiddleRowIndex(
  scrollTop,
  placeholderHeight,
  virtualHeight,
  windowHeight,
  rowHeight,
  count
) {
  const virtualScrollTop = realToVirtualScrollTop(
    scrollTop,
    placeholderHeight,
    virtualHeight,
    windowHeight
  )
  const middle = virtualScrollTop + windowHeight / 2
  const countIndex = Math.max(count - 1, 0)
  return Math.min(Math.max(Math.floor(middle / rowHeight), 0), countIndex)
}

/**
 * Converts a virtual scrollTop back to a real DOM scrollTop.
 */
export function virtualToRealScrollTop(
  virtualScrollTop,
  placeholderHeight,
  virtualHeight,
  windowHeight
) {
  const maxRealScroll = Math.max(placeholderHeight - windowHeight, 1)
  const maxVirtualScroll = Math.max(virtualHeight - windowHeight, 0)
  if (maxVirtualScroll === 0) return virtualScrollTop
  return (virtualScrollTop / maxVirtualScroll) * maxRealScroll
}

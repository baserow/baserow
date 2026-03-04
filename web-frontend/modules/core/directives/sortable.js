import { findScrollableParent } from '@baserow/modules/core/utils/dom'

/**
 * This directive can be used to enable vertical (or horizontal) drag and drop sorting
 * of an array of items within the same container, or across containers belonging to
 * the same `group`.
 *
 * When dragging starts, a ghost clone follows the cursor and a blue indicator line
 * shows the insertion point. The actual DOM order is not changed — only the `update`
 * callback is called with the new order so the caller can persist it.
 *
 * Options:
 *   - id        {*}        Unique identifier for this item (required)
 *   - update    {Function} Called on drop: (newOrder, oldOrder, draggedId, beforeId, toContainerId, fromContainerId)
 *   - handle    {string}   Optional CSS selector for the drag handle child element
 *   - enabled   {boolean}  When false, drag is disabled (default: true)
 *   - orientation {string} 'vertical' (default) or 'horizontal'
 *   - group     {string}   Optional group name to allow cross-container dragging
 *   - containerId {*}      Identifier for this element's container (used with group)
 *   - marginTop/Bottom/Left/Right {number} Offset applied when sizing the indicator
 *
 * Example:
 * ```
 * <div v-for="item in items" :key="item.id" v-sortable="{ id: item.id, update: onUpdate }">
 * </div>
 * ```
 */

// ---------------------------------------------------------------------------
// Helper: position the drop indicator in vertical or horizontal orientation.
// All coordinates are relative to `parentRect`.
// ---------------------------------------------------------------------------
function positionIndicator(el, indicator, all, before, beforeRect, parentRect) {
  const mt = el.sortableMarginTop || 0
  const mb = el.sortableMarginBottom || 0
  const ml = el.sortableMarginLeft || 0
  const mr = el.sortableMarginRight || 0

  if (all.length === 0) {
    // Empty container — fill the full parent area
    if (el.sortableOrientation === 'horizontal') {
      indicator.style.left = ml + 'px'
      indicator.style.top = mt + 'px'
      indicator.style.height = Math.max(0, parentRect.height - mt - mb) + 'px'
    } else {
      indicator.style.left = ml + 'px'
      indicator.style.width = Math.max(0, parentRect.width - ml - mr) + 'px'
      indicator.style.top = mt + 'px'
    }
    return
  }

  const afterRect = all[all.length - 1].getBoundingClientRect()
  const refRect = before ? beforeRect : afterRect

  if (el.sortableOrientation === 'horizontal') {
    const left =
      (before
        ? beforeRect.left - indicator.clientWidth / 2
        : afterRect.left + afterRect.width) -
      parentRect.left +
      el.sortableParent.scrollLeft +
      ml
    indicator.style.left = left + 'px'
    indicator.style.top = refRect.top - parentRect.top + mt + 'px'
    indicator.style.height = Math.max(0, refRect.height - mt - mb) + 'px'
  } else {
    const top =
      (before
        ? beforeRect.top - indicator.clientHeight / 2
        : afterRect.top + afterRect.height) -
      parentRect.top +
      el.sortableParent.scrollTop +
      mt
    indicator.style.top = top + 'px'
    indicator.style.left = refRect.left - parentRect.left + ml + 'px'
    indicator.style.width = Math.max(0, refRect.width - ml - mr) + 'px'
  }
}

// ---------------------------------------------------------------------------
// Helper: auto-scroll the scrollable parent when the cursor is near its edges.
// ---------------------------------------------------------------------------
function autoScroll(el, binding) {
  const isHorizontal = el.sortableOrientation === 'horizontal'
  const scrollParent = el.sortableScrollableParent
  const hasScroll = isHorizontal
    ? scrollParent.scrollWidth > scrollParent.clientWidth
    : scrollParent.scrollHeight > scrollParent.clientHeight

  if (!hasScroll) return

  const event = el.sortableLastMoveEvent
  const rect = scrollParent.getBoundingClientRect()
  const size = isHorizontal ? rect.right - rect.left : rect.bottom - rect.top
  const side = Math.ceil((size / 100) * 10)
  const mousePos = isHorizontal
    ? event.clientX - rect.left
    : event.clientY - rect.top
  const mouseOpp = size - mousePos
  let speed = 0

  if (mousePos < side) {
    speed = -(3 - Math.ceil((Math.max(0, mousePos) / side) * 3))
  } else if (mouseOpp < side) {
    speed = 3 - Math.ceil((Math.max(0, mouseOpp) / side) * 3)
  }

  if (speed !== 0) {
    el.sortableAutoScrolling = true
    if (isHorizontal) {
      scrollParent.scrollLeft += speed
    } else {
      scrollParent.scrollTop += speed
    }
    el.sortableScrollTimeout = setTimeout(() => {
      binding.dir.move(el, binding)
    }, 10)
  } else {
    el.sortableAutoScrolling = false
  }
}

// ---------------------------------------------------------------------------
// Helper: get all sortable sibling elements within a parent (excluding the
// indicator element).
// ---------------------------------------------------------------------------
function getSiblings(parent, indicator) {
  return [...parent.childNodes].filter(
    (e) => e !== indicator && e.nodeType === 1
  )
}

// ---------------------------------------------------------------------------
// Helper: ensure a container is relatively positioned so the absolute
// indicator renders correctly within it.
// ---------------------------------------------------------------------------
function ensureRelativePosition(container) {
  if (getComputedStyle(container).position === 'static') {
    container.style.position = 'relative'
  }
}

// ---------------------------------------------------------------------------
// Directive definition
// ---------------------------------------------------------------------------
export default {
  /**
   * Called when the directive must bind to the element. Registers the
   * mousedown event that starts the drag process.
   */
  beforeMount(el, binding) {
    binding.dir.updated(el, binding)
    el.sortableAutoScrolling = false

    el.mousedownEvent = (event) => {
      if (!el.sortableEnabled || event.button !== 0) return

      const handleSelector = binding.value.handle
      if (handleSelector) {
        const handle = event.target.closest(handleSelector)
        // Ensure the clicked handle belongs to this element (not a nested one)
        if (!handle || !el.contains(handle)) {
          return
        }
      }

      event.stopPropagation()

      el.sortableMoved = false
      el.sortableStartClientX = event.clientX
      el.sortableStartClientY = event.clientY
      el.classList.add('sortable-active-item')

      // Capture the originating parent for cross-container tracking
      el.sortableInitialParent = el.parentNode
      el.sortableParent = el.parentNode
      el.sortableScrollableParent =
        findScrollableParent(el.sortableParent) || el.sortableParent
      ensureRelativePosition(el.sortableParent)

      // Create the drop indicator
      el.sortableIndicator = document.createElement('div')
      el.sortableIndicator.classList.add('sortable-position-indicator')
      if (el.sortableOrientation === 'horizontal') {
        el.sortableIndicator.classList.add(
          'sortable-position-indicator--horizontal'
        )
      }
      el.sortableParent.insertBefore(
        el.sortableIndicator,
        el.sortableParent.firstChild
      )

      el.mouseMoveEvent = (event) => binding.dir.move(el, binding, event)
      window.addEventListener('mousemove', el.mouseMoveEvent)

      el.mouseUpEvent = () => binding.dir.up(el, binding)
      window.addEventListener('mouseup', el.mouseUpEvent)

      el.keydownEvent = (event) => {
        if (event.key === 'Escape') binding.dir.cancel(el)
      }
      document.body.addEventListener('keydown', el.keydownEvent)
    }

    el.addEventListener('mousedown', el.mousedownEvent)
  },

  /**
   * When the directive unmounts, remove all remaining event listeners and
   * cancel any in-progress drag.
   */
  unmounted(el, binding) {
    if (el.sortableMoved) {
      binding.dir.cancel(el)
    }
    el.removeEventListener('mousedown', el.mousedownEvent)
  },

  /**
   * Sync directive options to the element so they can be read by move/up/cancel.
   */
  updated(el, binding) {
    el.sortableId = binding.value.id
    el.sortableEnabled = binding.value.enabled ?? true
    el.sortableMarginLeft = binding.value.marginLeft
    el.sortableMarginRight = binding.value.marginRight
    el.sortableMarginTop = binding.value.marginTop
    el.sortableMarginBottom = binding.value.marginBottom
    el.sortableOrientation = binding.value.orientation || 'vertical'
    el.sortableGroup = binding.value.group
    el.sortableContainerId = binding.value.containerId
  },

  /**
   * Called on every mousemove while a drag is active. Positions the ghost clone
   * and the drop indicator, and triggers auto-scroll when near the edges.
   */
  move(el, binding, event = null) {
    if (event !== null) {
      event.preventDefault()
      el.sortableLastMoveEvent = event
    } else {
      event = el.sortableLastMoveEvent
    }

    // Guard: don't start moving until the cursor has moved at least 3px so that
    // a small accidental movement doesn't prevent a click from registering.
    if (!el.sortableMoved) {
      if (
        Math.abs(event.clientX - el.sortableStartClientX) > 3 ||
        Math.abs(event.clientY - el.sortableStartClientY) > 3
      ) {
        el.sortableMoved = true
        el.classList.add('sortable-dragging-item')

        // Create a fixed ghost clone that follows the cursor.
        el.sortableGhostElement = el.cloneNode(true)
        const rect = el.getBoundingClientRect()
        el.sortableGhostElement.classList.add('sortable-ghost-element')
        el.sortableGhostElement.style.width = rect.width + 'px'
        el.sortableGhostElement.style.height = rect.height + 'px'
        el.sortableGhostOffsetX = event.clientX - rect.left
        el.sortableGhostOffsetY = event.clientY - rect.top
        document.body.appendChild(el.sortableGhostElement)
      } else {
        return
      }
    }

    // Move ghost with the cursor.
    if (el.sortableGhostElement) {
      el.sortableGhostElement.style.left =
        event.clientX - el.sortableGhostOffsetX + 'px'
      el.sortableGhostElement.style.top =
        event.clientY - el.sortableGhostOffsetY + 'px'
    }

    // Cross-container: detect if the cursor has moved into a different container
    // belonging to the same sortable group and switch `sortableParent` to it.
    if (el.sortableGroup) {
      // Temporarily hide the indicator and ghost so elementFromPoint sees through them.
      el.sortableIndicator.style.display = 'none'
      if (el.sortableGhostElement)
        el.sortableGhostElement.style.pointerEvents = 'none'

      const target = document.elementFromPoint(event.clientX, event.clientY)

      el.sortableIndicator.style.display = ''
      if (el.sortableGhostElement)
        el.sortableGhostElement.style.pointerEvents = ''

      if (target) {
        const groupContainer = target.closest(
          `[data-sortable-group="${el.sortableGroup}"]`
        )
        if (groupContainer && groupContainer !== el.sortableParent) {
          // Remove sorting classes from the old parent's children.
          getSiblings(el.sortableParent, el.sortableIndicator).forEach((s) =>
            s.classList.remove('sortable-sorting-item')
          )

          el.sortableParent = groupContainer
          el.sortableScrollableParent =
            findScrollableParent(groupContainer) || groupContainer
          ensureRelativePosition(groupContainer)
          groupContainer.insertBefore(
            el.sortableIndicator,
            groupContainer.firstChild
          )
        }
      }
    }

    // Disable pointer events on all siblings to get smooth hover behaviour.
    const all = getSiblings(el.sortableParent, el.sortableIndicator)
    all.forEach((s) => s.classList.add('sortable-sorting-item'))

    const parentRect = el.sortableParent.getBoundingClientRect()

    // Determine before which sibling the dragged item would be inserted.
    let before = null
    let beforeRect = {}
    for (let i = 0; i < all.length; i++) {
      beforeRect = all[i].getBoundingClientRect()
      const isHorizontal = el.sortableOrientation === 'horizontal'
      const center = isHorizontal
        ? beforeRect.left + beforeRect.width / 2
        : beforeRect.top + beforeRect.height / 2
      const pos = isHorizontal ? event.clientX : event.clientY
      if (pos < center) {
        before = all[i]
        break
      }
    }

    el.sortableBeforeElement = before

    // Position the blue indicator line.
    positionIndicator(
      el,
      el.sortableIndicator,
      all,
      before,
      beforeRect,
      parentRect
    )

    // Auto-scroll if the cursor is near the edge of the scrollable container.
    if (!el.sortableAutoScrolling) {
      autoScroll(el, binding)
    }
  },

  /**
   * Called when the user releases the mouse. Calculates the new item order and
   * fires the `update` callback if the position changed.
   */
  up(el, binding) {
    binding.dir.cancel(el)

    if (!el.sortableMoved) return
    el.sortableMoved = false

    // Suppress any click event that might fire immediately after mouseup so that
    // clicking overlapping elements after a drop doesn't trigger unexpected actions.
    const suppressClick = (event) => {
      event.stopPropagation()
      window.removeEventListener('click', suppressClick, true)
    }
    window.addEventListener('click', suppressClick, true)
    setTimeout(() => window.removeEventListener('click', suppressClick, true))

    const oldOrder = [...el.sortableParent.childNodes]
      .filter((e) => e.nodeType === 1)
      .map((e) => e.sortableId)

    const newOrder = oldOrder.filter((id) => id !== el.sortableId)
    const targetIndex = el.sortableBeforeElement
      ? newOrder.findIndex((id) => id === el.sortableBeforeElement.sortableId)
      : newOrder.length

    if (targetIndex === -1) return

    newOrder.splice(targetIndex, 0, el.sortableId)

    const orderUnchanged = JSON.stringify(oldOrder) === JSON.stringify(newOrder)
    const containerUnchanged = el.sortableParent === el.sortableInitialParent

    if (orderUnchanged && containerUnchanged) return

    binding.value.update(
      newOrder,
      oldOrder,
      el.sortableId,
      el.sortableBeforeElement?.sortableId || null,
      el.sortableParent.dataset.sortableContainerId,
      el.sortableInitialParent.dataset.sortableContainerId
    )
  },

  /**
   * Cancel a drag in progress: remove the indicator and ghost, clear classes,
   * and remove all temporary event listeners.
   */
  cancel(el) {
    clearTimeout(el.sortableScrollTimeout)
    el.sortableAutoScrolling = false

    if (el.sortableIndicator?.parentNode) {
      el.sortableIndicator.parentNode.removeChild(el.sortableIndicator)
    }

    if (el.sortableGhostElement?.parentNode) {
      el.sortableGhostElement.parentNode.removeChild(el.sortableGhostElement)
      el.sortableGhostElement = null
    }

    if (el.sortableParent) {
      getSiblings(el.sortableParent, el.sortableIndicator).forEach((s) =>
        s.classList.remove('sortable-sorting-item')
      )
    }

    el.classList.remove('sortable-dragging-item')
    el.classList.remove('sortable-active-item')

    window.removeEventListener('mouseup', el.mouseUpEvent)
    window.removeEventListener('mousemove', el.mouseMoveEvent)
    document.body.removeEventListener('keydown', el.keydownEvent)
  },
}

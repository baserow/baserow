import { findScrollableParent } from '@baserow/modules/core/utils/dom'

/**
 * This directive can by used to enable vertical drag and drop sorting of an array of
 * items. When the dragging starts, it simply shows a target position and will call a
 * function when the item has been dropped. It will not actually change the order of
 * the items, but it will only show the drag and drop effect and calculates the new
 * order of the items. The actual updating has to happen in the update function.
 *
 * Optionally a handle selector can be provided by doing
 * `v-sortable="{ id: item.id, update: order, handle: '.child-element' }"`.
 *
 * Example:
 *
 * ```
 * <div
 *   v-for="item in items"
 *   :key="item.id"
 *   v-sortable="{ id: item.id, update: onUpdate }"
 * ></div>
 *
 * export default {
 *   data() {
 *     return {
 *       items: [{'id': 25, order: 1}, {'id': 27, order: 2}, {'id': 30, order: 3}]
 *     }
 *   },
 *   methods: {
 *     onUpdate(itemIds) {
 *       console.log(itemIds) // [25, 27, 30]
 *     },
 *   },
 * }
 * ```
 */
let parent
let scrollableParent
let indicator
let ghostElement

export default {
  /**
   * Called when the directive must bind to the element. It will register the
   * mousedown event on the element, which is used to start the drag and drop
   * process.
   */
  beforeMount(el, binding) {
    binding.dir.updated(el, binding)
    el.sortableAutoScrolling = false

    const mousedownElement = binding.value.handle
      ? el.querySelector(binding.value.handle)
      : el

    el.mousedownEvent = (event) => {
      if (!el.sortableEnabled || event.button !== 0) {
        return
      }

      el.sortableMoved = false
      el.sortableStartClientX = event.clientX
      el.sortableStartClientY = event.clientY

      el.classList.add('sortable-active-item')

      el.mouseMoveEvent = (event) => binding.dir.move(el, binding, event)
      window.addEventListener('mousemove', el.mouseMoveEvent)

      el.mouseUpEvent = (event) => binding.dir.up(el, binding, event)
      window.addEventListener('mouseup', el.mouseUpEvent)

      el.keydownEvent = (event) => {
        if (event.key === 'Escape') {
          // When the user presses the escape key we want to cancel the action
          binding.dir.cancel(el, event)
        }
      }
      document.body.addEventListener('keydown', el.keydownEvent)

      parent = el.parentNode
      scrollableParent = findScrollableParent(parent) || parent

      // If the parent container is not positioned, add the position automatically.
      if (getComputedStyle(parent).position === 'static') {
        parent.style.position = 'relative'
      }

      indicator = document.createElement('div')
      indicator.classList.add('sortable-position-indicator')
      if (el.sortableOrientation === 'horizontal') {
        indicator.classList.add('sortable-position-indicator--horizontal')
      }
      parent.insertBefore(indicator, parent.firstChild)
    }
    mousedownElement.addEventListener('mousedown', el.mousedownEvent)
  },
  /**
   * When the directive must unbind from the element, we will remove all the events
   * that could have been added.
   */
  unmounted(el, binding) {
    if (el.sortableMoved) {
      binding.dir.cancel(el)
    }

    const mousedownElement = binding.value.handle
      ? el.querySelector(binding.value.handle)
      : el
    mousedownElement.removeEventListener('mousedown', el.mousedownEvent)
  },
  updated(el, binding) {
    el.sortableId = binding.value.id
    el.sortableEnabled =
      binding.value.enabled || binding.value.enabled === undefined
    el.sortableMarginLeft = binding.value.marginLeft
    el.sortableMarginRight = binding.value.marginRight
    el.sortableMarginTop = binding.value.marginTop
    el.sortableMarginBottom = binding.value.marginBottom
    el.sortableOrientation = binding.value.orientation || 'vertical'
  },
  /**
   * Called when the user moves the mouse when the dragging of the element has
   * started. It will calculate the target indicator position and saves before which
   * element it must be placed.
   */
  move(el, binding, event = null, startAutoScroll = true) {
    if (event !== null) {
      event.preventDefault()
      el.sortableLastMoveEvent = event
    } else {
      event = el.sortableLastMoveEvent
    }

    // Sometimes the user could accidentally drag the element one or two pixels while
    // clicking it. Because it could be annoying that the click doesn't work because
    // the moving state started, we check here if the user has at least dragged
    // the element 3 pixels vertically or horizontally before starting the moved state.
    if (!el.sortableMoved) {
      if (
        Math.abs(event.clientX - el.sortableStartClientX) > 3 ||
        Math.abs(event.clientY - el.sortableStartClientY) > 3
      ) {
        el.sortableMoved = true
        el.classList.add('sortable-dragging-item')

        // Create the ghost element
        ghostElement = el.cloneNode(true)
        const rect = el.getBoundingClientRect()
        ghostElement.classList.add('sortable-ghost-element')
        ghostElement.style.width = rect.width + 'px'
        ghostElement.style.height = rect.height + 'px'
        // Save offsets to keep the mouse positioned identically relative to the ghost
        el.sortableGhostOffsetX = event.clientX - rect.left
        el.sortableGhostOffsetY = event.clientY - rect.top

        ghostElement.style.left = event.clientX - el.sortableGhostOffsetX + 'px'
        ghostElement.style.top = event.clientY - el.sortableGhostOffsetY + 'px'
        document.body.appendChild(ghostElement)
      } else {
        return
      }
    }

    if (ghostElement) {
      ghostElement.style.left = event.clientX - el.sortableGhostOffsetX + 'px'
      ghostElement.style.top = event.clientY - el.sortableGhostOffsetY + 'px'
    }

    // Set pointer events to none because that will prevent hover and click
    // effects.
    const all = [...parent.childNodes].filter(
      (e) => e !== indicator && e.nodeType === 1
    )

    // Add the `sortable-sorting-item` which disables the pointer events and user
    // select of all the sortable items. This will give a smoother user experience
    // as the user can't accidentally click the item and can't select the text while
    // dragging.
    all.forEach((s) => {
      s.classList.add('sortable-sorting-item')
    })

    const parentRect = parent.getBoundingClientRect()

    // Using the mouse position and the position of the items we can calculate
    // before which item the dragging item must be placed. If the position of the
    // mouse is above the vertical center (or left of horizontal center) of the
    // element, it must be placed before that item.
    let before = null
    let beforeRect = {}
    for (let i = 0; i < all.length; i++) {
      beforeRect = all[i].getBoundingClientRect()
      if (el.sortableOrientation === 'horizontal') {
        if (event.clientX < beforeRect.left + beforeRect.width / 2) {
          before = all[i]
          break
        }
      } else {
        if (event.clientY < beforeRect.top + beforeRect.height / 2) {
          before = all[i]
          break
        }
      }
    }

    // Save the element where the dragging item must be placed before so that the
    // new order can be calculated when the user releases the mouse.
    el.sortableBeforeElement = before

    // Calculate the target indicator position based on the position of the
    // beforeElement. If the beforeElement is null, it means that the dragging
    // element must be moved to the end.
    const elementRect = el.getBoundingClientRect()
    const afterRect = all[all.length - 1].getBoundingClientRect()

    if (el.sortableOrientation === 'horizontal') {
      const left =
        (before
          ? beforeRect.left - indicator.clientWidth / 2
          : afterRect.left + afterRect.width) -
        parentRect.left +
        parent.scrollLeft +
        (el.sortableMarginLeft || 0)
      const top = elementRect.top - parentRect.top
      indicator.style.left = left + 'px'
      indicator.style.top = top + (el.sortableMarginTop || 0) + 'px'
      indicator.style.height =
        elementRect.height -
        (el.sortableMarginTop || 0) -
        (el.sortableMarginBottom || 0) +
        'px'
    } else {
      const top =
        (before
          ? beforeRect.top - indicator.clientHeight / 2
          : afterRect.top + afterRect.height) -
        parentRect.top +
        parent.scrollTop +
        (el.sortableMarginTop || 0)
      const left = elementRect.left - parentRect.left
      indicator.style.left = left + (el.sortableMarginLeft || 0) + 'px'
      indicator.style.width =
        elementRect.width -
        (el.sortableMarginLeft || 0) -
        (el.sortableMarginRight || 0) +
        'px'
      indicator.style.top = top + 'px'
    }

    // If the user is not already auto scrolling, which happens while dragging and
    // moving the element close to the end of the view port at the top or bottom
    // side (or left and right for horizontal), we might need to initiate that process.
    if (el.sortableOrientation === 'horizontal') {
      if (
        scrollableParent.scrollWidth > scrollableParent.clientWidth &&
        (!el.sortableAutoScrolling || !startAutoScroll)
      ) {
        const scrollableParentRect = scrollableParent.getBoundingClientRect()
        const parentWidth =
          scrollableParentRect.right - scrollableParentRect.left
        const side = Math.ceil((parentWidth / 100) * 10)
        const autoScrollMouseLeft = event.clientX - scrollableParentRect.left
        const autoScrollMouseRight = parentWidth - autoScrollMouseLeft
        let speed = 0

        if (autoScrollMouseLeft < side) {
          speed = -(
            3 - Math.ceil((Math.max(0, autoScrollMouseLeft) / side) * 3)
          )
        } else if (autoScrollMouseRight < side) {
          speed = 3 - Math.ceil((Math.max(0, autoScrollMouseRight) / side) * 3)
        }

        if (speed !== 0) {
          el.sortableAutoScrolling = true
          scrollableParent.scrollLeft += speed
          el.sortableScrollTimeout = setTimeout(() => {
            binding.dir.move(el, binding, null, false)
          }, 10)
        } else {
          el.sortableAutoScrolling = false
        }
      }
    } else {
      if (
        scrollableParent.scrollHeight > scrollableParent.clientHeight &&
        (!el.sortableAutoScrolling || !startAutoScroll)
      ) {
        const scrollableParentRect = scrollableParent.getBoundingClientRect()
        const parentHeight =
          scrollableParentRect.bottom - scrollableParentRect.top
        const side = Math.ceil((parentHeight / 100) * 10)
        const autoScrollMouseTop = event.clientY - scrollableParentRect.top
        const autoScrollMouseBottom = parentHeight - autoScrollMouseTop
        let speed = 0

        if (autoScrollMouseTop < side) {
          speed = -(3 - Math.ceil((Math.max(0, autoScrollMouseTop) / side) * 3))
        } else if (autoScrollMouseBottom < side) {
          speed = 3 - Math.ceil((Math.max(0, autoScrollMouseBottom) / side) * 3)
        }

        // If the speed is either a positive or negative, so not 0, we know that we
        // need to start auto scrolling.
        if (speed !== 0) {
          el.sortableAutoScrolling = true
          scrollableParent.scrollTop += speed
          el.sortableScrollTimeout = setTimeout(() => {
            binding.dir.move(el, binding, null, false)
          }, 10)
        } else {
          el.sortableAutoScrolling = false
        }
      }
    }
  },
  /**
   * Called when the user releases the mouse after the dragging of the element has
   * started. It will check calculate the new order of all items based on the last
   * beforeElement element saved by the move method. If the item has changed
   * position, the update function is called which needs to change the actual order
   * of the items.
   */
  up(el, binding) {
    binding.dir.cancel(el, binding)

    if (!el.sortableMoved) {
      return
    }

    el.sortableMoved = false

    // It could be that the element or a child element has a click handler. When the
    // user releases the mouse pointer, that click event could also be triggered
    // which we don't because we are dragging the element instead of clicking on it
    // directly. This makes sure that when releasing the mouse pointer, that click
    // event is stopped.
    const preventOtherClickEvent = (event) => {
      event.stopPropagation()
      window.removeEventListener('click', preventOtherClickEvent, true)
    }
    window.addEventListener('click', preventOtherClickEvent, true)
    // Remove the event because it could be that the user wants to click on the
    // element right after it has been moved.
    setTimeout(() => {
      window.removeEventListener('click', preventOtherClickEvent, true)
    })

    const oldOrder = [...parent.childNodes]
      .filter((e) => e.nodeType === 1)
      .map((e) => e.sortableId)
    const newOrder = oldOrder.filter((id) => id !== el.sortableId)
    const targetIndex = el.sortableBeforeElement
      ? newOrder.findIndex((id) => id === el.sortableBeforeElement.sortableId)
      : newOrder.length

    if (targetIndex === -1) {
      return
    }

    newOrder.splice(targetIndex, 0, el.sortableId)

    if (JSON.stringify(oldOrder) === JSON.stringify(newOrder)) {
      return
    }

    binding.value.update(
      newOrder,
      oldOrder,
      el.sortableId,
      el.sortableBeforeElement?.sortableId || null
    )
  },
  /**
   * Cancels the sorting by removing the target indicator, sorting classes and event
   * listeners.
   */
  cancel(el) {
    clearTimeout(el.sortableScrollTimeout)

    if (indicator.parentNode) {
      indicator.parentNode.removeChild(indicator)
    }

    if (ghostElement && ghostElement.parentNode) {
      ghostElement.parentNode.removeChild(ghostElement)
      ghostElement = null
    }

    const all = [...parent.childNodes].filter((e) => e.nodeType === 1)
    all.forEach((s) => {
      s.classList.remove('sortable-sorting-item')
    })
    el.classList.remove('sortable-dragging-item')
    el.classList.remove('sortable-active-item')

    window.removeEventListener('mouseup', el.mouseUpEvent)
    window.removeEventListener('mousemove', el.mouseMoveEvent)
    document.body.removeEventListener('keydown', el.keydownEvent)
  },
}

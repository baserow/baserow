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

export default {
  /**
   * Called when the directive must bind to the element. It will register the
   * mousedown event on the element, which is used to start the drag and drop
   * process.
   */
  bind(el, binding) {
    binding.def.update(el, binding)
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

      el.mouseMoveEvent = (event) => binding.def.move(el, binding, event)
      window.addEventListener('mousemove', el.mouseMoveEvent)

      el.mouseUpEvent = (event) => binding.def.up(el, binding, event)
      window.addEventListener('mouseup', el.mouseUpEvent)

      el.keydownEvent = (event) => {
        if (event.key === 'Escape') {
          // When the user presses the escape key we want to cancel the action
          binding.def.cancel(el, event)
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
      parent.insertBefore(indicator, parent.firstChild)
    }
    mousedownElement.addEventListener('mousedown', el.mousedownEvent)
  },
  /**
   * When the directive must unbind from the element, we will remove all the events
   * that could have been added.
   */
  unbind(el, binding) {
    if (el.sortableMoved) {
      binding.def.cancel(el)
    }

    const mousedownElement = binding.value.handle
      ? el.querySelector(binding.value.handle)
      : el
    mousedownElement.removeEventListener('mousedown', el.mousedownEvent)
  },
  update(el, binding) {
    el.sortableId = binding.value.id
    el.sortableEnabled =
      binding.value.enabled || binding.value.enabled === undefined
    el.sortableMarginLeft = binding.value.marginLeft
    el.sortableMarginRight = binding.value.marginRight
    el.sortableMarginTop = binding.value.marginTop
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
      } else {
        return
      }
    }

    // Set pointer events to none because that will prevent hover and click
    // effects.
    const all = [...parent.childNodes].filter((e) => e !== indicator)

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
    // mouse is above the vertical center of the element, it must be placed before
    // that item.
    let before = null
    let beforeRect = {}
    for (let i = 0; i < all.length; i++) {
      beforeRect = all[i].getBoundingClientRect()
      if (event.clientY < beforeRect.top + beforeRect.height / 2) {
        before = all[i]
        break
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

    // If the user is not already auto scrolling, which happens while dragging and
    // moving the element close to the end of the view port at the top or bottom
    // side, we might need to initiate that process.
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
          binding.def.move(el, binding, null, false)
        }, 10)
      } else {
        el.sortableAutoScrolling = false
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
    binding.def.cancel(el, binding)

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

    const oldOrder = [...parent.childNodes].map((e) => e.sortableId)
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

    const all = parent.childNodes
    all.forEach((s) => {
      s.classList.remove('sortable-sorting-item')
    })

    window.removeEventListener('mouseup', el.mouseUpEvent)
    window.removeEventListener('mousemove', el.mouseMoveEvent)
    document.body.removeEventListener('keydown', el.keydownEvent)
  },
}

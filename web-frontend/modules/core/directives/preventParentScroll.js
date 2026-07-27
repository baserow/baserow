/**
 * Because the scroll directive uses the wheel event it prevents all other elements
 * being able to scroll. This directive can be used on a child element that supports
 * scrolling, it makes sure that scrolling works and so that it doesn't scroll the
 * parent.
 *
 * The binding value controls the behavior:
 * - `true` or no value: always stop propagation.
 * - `false`: directive is disabled.
 * - `WHEN_SCROLLABLE`: only stop propagation if the element actually overflows.
 *   This must be checked at event time because the overflow state changes with the
 *   content. Use this when the parent should still scroll while the element has
 *   nothing to scroll itself, for example the selected link row cell in the grid
 *   view.
 */

export const WHEN_SCROLLABLE = 'when-scrollable'

const addEventListeners = (el, mode) => {
  el.preventParentScrollDirectiveEvent = (event) => {
    if (
      mode === WHEN_SCROLLABLE &&
      el.scrollHeight <= el.clientHeight &&
      el.scrollWidth <= el.clientWidth
    ) {
      return
    }
    event.stopPropagation()
  }
  el.addEventListener('wheel', el.preventParentScrollDirectiveEvent)
  el.addEventListener('touchstart', el.preventParentScrollDirectiveEvent)
  el.addEventListener('touchend', el.preventParentScrollDirectiveEvent)
  el.addEventListener('touchmove', el.preventParentScrollDirectiveEvent)
}

const removeEventListeners = (el) => {
  el.removeEventListener('wheel', el.preventParentScrollDirectiveEvent)
  el.removeEventListener('touchstart', el.preventParentScrollDirectiveEvent)
  el.removeEventListener('touchend', el.preventParentScrollDirectiveEvent)
  el.removeEventListener('touchmove', el.preventParentScrollDirectiveEvent)
}

export default {
  beforeMount(el, binding) {
    const value = binding.value !== undefined ? binding.value : true
    if (value !== false) {
      addEventListeners(el, value)
    }
  },
  updated(el, binding) {
    if (binding.value !== binding.oldValue) {
      removeEventListeners(el)
      const value = binding.value !== undefined ? binding.value : true
      if (value !== false) {
        addEventListeners(el, value)
      }
    }
  },
  unmounted(el) {
    removeEventListeners(el)
  },
}

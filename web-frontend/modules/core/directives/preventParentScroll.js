/**
 * Because the scroll directive uses the wheel event it prevents all other elements
 * being able to scroll. This directive can be used on a child element that supports
 * scrolling, it makes sure that scrolling works and so that it doesn't scroll the
 * parent.
 *
 * The `whenScrollable` modifier makes stopping the propagation conditional: the
 * event only stops if the element actually overflows. This must be checked at
 * event time because the overflow state changes with the content. Use this when
 * the parent should still scroll while the element has nothing to scroll itself,
 * for example the selected link row cell in the grid view.
 */

const addEventListeners = (el, whenScrollable) => {
  el.preventParentScrollDirectiveEvent = (event) => {
    if (
      whenScrollable &&
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
    const active = binding.value !== undefined ? binding.value : true
    if (active) {
      addEventListeners(el, !!binding.modifiers.whenScrollable)
    }
  },
  updated(el, binding) {
    if (binding.value !== binding.oldValue) {
      if (binding.value) {
        addEventListeners(el, !!binding.modifiers.whenScrollable)
      } else {
        removeEventListeners(el)
      }
    }
  },
  unmounted(el) {
    removeEventListeners(el)
  },
}

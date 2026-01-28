/**
 * Because the scroll directive uses the wheel event it prevents all other elements
 * being able to scroll. This directive can be used on a child element that supports
 * scrolling, it makes sure that scrolling works and so that it doesn't scroll the
 * parent.
 */

const addEventListeners = (el) => {
  el.preventParentScrollDirectiveEvent = (event) => {
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
      addEventListeners(el)
    }
  },
  updated(el, binding) {
    if (binding.value !== binding.oldValue) {
      if (binding.value) {
        addEventListeners(el)
      } else {
        removeEventListeners(el)
      }
    }
  },
  unmounted(el) {
    removeEventListeners(el)
  },
}

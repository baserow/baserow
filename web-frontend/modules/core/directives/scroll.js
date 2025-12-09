/**
 * A helper directive that will fire the provided binding function every time the
 * user scrolls inside an element. The reason why you would use this and not the native
 * scroll event is because the element doesn't need to have a overflow scroll. The
 * parameters of the function are going to be the change in pixels based on the
 * users scroll action.
 *
 * Example:
 * <div v-scroll="scroll" style="overflow: hidden; width: 200px; height: 200px;">
 *   <div style="width: 2000px; height: 2000px;"></div>
 * </div>
 * ...
 * methods: {
 *   scroll(pixelY, pixelX) {
 *     // Implement code here that changes the scrollTop and scrollLeft of the element.
 *   }
 * }
 *
 * @TODO this might have to made a bit more cross browser supported, but that needs
 *       to be tested.
 */
export default {
  beforeMount(el, binding) {
    const DOM_DELTA_PIXEL = 0
    const DOM_DELTA_LINE = 1
    el.scrollDirectiveEvent = (event) => {
      const deltaMode = event.deltaMode
      let { deltaY, deltaX } = event

      // shiftKey enable the horizontal scroll, so swap deltaX and deltaY.
      // Mac OSX already swap the values and set DeltaY to 0, so no need to swap them again.
      if (event.shiftKey && deltaY !== 0) {
        deltaX = deltaY
        deltaY = 0
      }

      let pixelY = 0
      let pixelX = 0

      // Most browsers will provide the scrolling delta as pixels.
      if (deltaMode === DOM_DELTA_PIXEL) {
        pixelY = deltaY
        pixelX = deltaX
      }

      // Firefox uses the DOM_DELTA_LINE mode when scrolling with the scrollwheel.
      if (deltaMode === DOM_DELTA_LINE) {
        pixelY = deltaY * 10
        pixelX = deltaX * 10
      }

      if (pixelY === 0 && pixelX === 0) {
        return
      }

      const shouldNotPreventDefault = binding.value(pixelY, pixelX)

      if (shouldNotPreventDefault !== true) {
        event.preventDefault()
      }
    }
    el.addEventListener('wheel', el.scrollDirectiveEvent)

    // The touch equivalent for the wheel event. It doesn't offer a native
    // experience for the user, but it does make it usable.
    let touching = false
    let lastX = 0
    let lastY = 0
    el.scrollTouchStartEvent = (event) => {
      touching = true
      const touches = event.changedTouches
      lastX = Math.round(touches[0].pageX)
      lastY = Math.round(touches[0].pageY)
    }
    el.scrollTouchMoveEvent = (event) => {
      if (touching) {
        if (event.cancelable) {
          event.preventDefault()
        }

        const touches = event.targetTouches
        const eventY = Math.round(touches[0].pageY)
        const eventX = Math.round(touches[0].pageX)

        if (eventY !== lastY || eventX !== lastX) {
          const diffY = lastY - eventY
          const diffX = lastX - eventX
          binding.value(diffY, diffX)

          lastY = eventY
          lastX = eventX
        }
      }
    }
    el.scrollTouchEndEvent = () => {
      touching = false
    }
    el.addEventListener('touchstart', el.scrollTouchStartEvent)
    el.addEventListener('touchmove', el.scrollTouchMoveEvent)
    el.addEventListener('touchend', el.scrollTouchEndEvent)
  },
  unmounted(el) {
    el.removeEventListener('wheel', el.scrollDirectiveEvent)
    el.removeEventListener('touchstart', el.scrollTouchStartEvent)
    el.removeEventListener('touchmove', el.scrollTouchMoveEvent)
    el.removeEventListener('touchend', el.scrollTouchEndEvent)
  },
}

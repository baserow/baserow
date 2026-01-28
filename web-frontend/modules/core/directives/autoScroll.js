/**
 * A directive that helps with auto scrolling when the mouse pointer reaches the
 * edge of the element.
 *
 * v-auto-scroll="{
 *   // Indicates whether we should scroll vertically or horizontally by providing
 *   // `vertical` or `horizontal`.
 *   orientation: 'vertical'
 *   // Dynamic indication if the auto scrolling is enabled. This is typically used
 *   // we should only auto scroll if dragging a certain element.
 *   enabled: () => true,
 *   // The speed that should be scrolled with.
 *   speed: 3,
 *   // Indicates the percentage of the edges that should trigger the auto
 *   // scrolling. If 10 is provided, then the auto scrolling starts when the mouse
 *   // pointer is in 10% of the edge of the element.
 *   padding: 10,
 *   // The element that should be scrolled in. By default this is the element
 *   // that's binding by the directive, but it can optionally be changed.
 *   scrollElement: () => DOMElement
 * }"
 */
export default {
  beforeMount(el, binding) {
    binding.dir.updated(el, binding)

    el.autoScrollTimeout = null
    el.autoScrollLastMoveEvent = null

    const autoscrollLoop = () => {
      if (!el.autoScrollConfig.enabled()) {
        clearTimeout(el.autoScrollTimeout)
        el.autoScrollTimeout = null
        return
      }

      const scrollElement = el.autoScrollConfig.scrollElement()
      const rect = scrollElement.getBoundingClientRect()
      let size
      let autoScrollMouseStart

      if (el.autoScrollConfig.orientation === 'horizontal') {
        size = rect.right - rect.left
        autoScrollMouseStart = el.autoScrollLastMoveEvent.clientX - rect.left
      } else {
        size = rect.bottom - rect.top
        autoScrollMouseStart = el.autoScrollLastMoveEvent.clientY - rect.top
      }

      const autoScrollMouseEnd = size - autoScrollMouseStart
      const side = Math.ceil((size / 100) * el.autoScrollConfig.padding)

      let speed = 0
      if (autoScrollMouseStart < side) {
        speed = -(
          el.autoScrollConfig.speed -
          Math.ceil(
            (Math.max(0, autoScrollMouseStart) / side) *
              el.autoScrollConfig.speed
          )
        )
      } else if (autoScrollMouseEnd < side) {
        speed =
          el.autoScrollConfig.speed -
          Math.ceil(
            (Math.max(0, autoScrollMouseEnd) / side) * el.autoScrollConfig.speed
          )
      }

      // If the speed is either a positive or negative, so not 0, we know that we
      // need to start auto scrolling.
      if (speed !== 0) {
        // Only update the element if the `onScroll` functions returns `true`. This
        // is because in some cases, scrolling is handled in another way. This is
        // for example the case with the `GridView`.
        if (el.autoScrollConfig.onScroll(speed)) {
          if (el.autoScrollConfig.orientation === 'horizontal') {
            scrollElement.scrollLeft += speed
          } else {
            scrollElement.scrollTop += speed
          }
        }
        el.autoScrollTimeout = setTimeout(() => {
          autoscrollLoop()
        }, 2)
      } else {
        clearTimeout(el.autoScrollTimeout)
        el.autoScrollTimeout = null
      }
    }
    el.autoScrollMouseMoveEvent = (event) => {
      el.autoScrollLastMoveEvent = event

      if (el.autoScrollTimeout === null) {
        autoscrollLoop()
      }
    }
    el.addEventListener('mousemove', el.autoScrollMouseMoveEvent)
  },
  updated(el, binding) {
    const defaultEnabled = () => true
    const defaultScrollElement = () => el
    const defaultOnScroll = () => true
    el.autoScrollConfig = {
      orientation: binding.value.orientation || 'vertical',
      enabled: binding.value.enabled || defaultEnabled,
      speed: binding.value.speed || 3,
      padding: binding.value.padding || 10,
      scrollElement: binding.value.scrollElement || defaultScrollElement,
      onScroll: binding.value.onScroll || defaultOnScroll,
    }
  },
  unmounted(el) {
    el.removeEventListener('mousemove', el.autoScrollMouseMoveEvent)
  },
}

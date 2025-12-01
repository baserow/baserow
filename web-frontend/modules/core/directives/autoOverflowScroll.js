import ResizeObserver from 'resize-observer-polyfill'

/**
 * This directive does the same as `overflow: auto;`, so it will make sure that the
 * scrollbars are visible when the content does not fit inside the element. It
 * expects the element to have `overflow: scroll;` by default which will always show
 * the scrollbars. If the content does fit, it will add the class `prevent-scroll`
 * which adds `overflow: hidden !important;` which will remove the scrollbars.
 *
 * The reason why you would want this could be when `overflow: auto;` is causing
 * scrollbar width side effects. It could for example be that the width of the
 * element depends on the width of the children. In that case `overflow: auto;`
 * might not work as the scrollbar width is not added to the total width of the
 * element. `overflow: scroll` does add the scrollbar width.
 *
 * Optionally, the directive accepts a boolean value to enable or disable it. By
 * default, the value is `true`, so then it's enabled.
 */
export default {
  bind(el, binding) {
    const value = binding.value === undefined ? true : binding.value
    if (!value) {
      binding.def.removeListeners(el)
    } else if (value) {
      binding.def.addListeners(el)
    }
  },
  unbind(el, binding) {
    binding.def.removeListeners(el)
  },
  update(el, binding) {
    const value = binding.value === undefined ? true : binding.value
    if (el.autoOverflowScrollHeightObserverBinded && !value) {
      binding.def.removeListeners(el)
    } else if (!el.autoOverflowScrollHeightObserverBinded && value) {
      binding.def.addListeners(el)
    }
  },
  addListeners(el) {
    // Flag to track when we're updating to prevent feedback loops
    el.autoOverflowScrollIsUpdating = false

    el.autoOverflowScrollHeightObserverFunction = () => {
      // Ignore observer callbacks if we are currently adding or removing the
      // 'prevent-scroll' class, this is to prevent a feedback loop where the
      // observer reacts to our own changes.
      if (el.autoOverflowScrollIsUpdating) {
        return
      }

      // Add a small tolerance to prevent feedback loops when scrollHeight
      // and clientHeight are very close (e.g., due to scrollbar width changes)
      const pixelTolerance = 2
      const hasPreventScroll = el.classList.contains('prevent-scroll')

      // We prevent the scroll if the content fits within the element (within
      // the pixel tolerance)
      const shouldPreventScroll = hasPreventScroll
        ? el.scrollHeight <= el.clientHeight + pixelTolerance
        : el.scrollHeight <= el.clientHeight

      // Only update if class needs to actually change
      if (shouldPreventScroll === hasPreventScroll) {
        return
      }

      // A change is needed, set the flag to indicate we're updating.
      el.autoOverflowScrollIsUpdating = true
      if (shouldPreventScroll) {
        el.classList.add('prevent-scroll')
      } else {
        el.classList.remove('prevent-scroll')
      }
      // Reset flag after browser has processed the change
      // We do this twice because the first frame can change the layout,
      // so by the second frame, we should be done, so we can flag that
      // we're done updating with `autoOverflowScrollIsUpdating = false`.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.autoOverflowScrollIsUpdating = false
        })
      })
    }
    el.autoOverflowScrollHeightObserver = new ResizeObserver(
      el.autoOverflowScrollHeightObserverFunction
    )
    el.autoOverflowScrollHeightObserver.observe(el)
    el.autoOverflowScrollHeightObserverBinded = true
  },
  removeListeners(el) {
    el.autoOverflowScrollHeightObserver?.unobserve(el)
    el.autoOverflowScrollHeightObserverBinded = false
  },
}

import _ from 'lodash'
import { onClickOutside } from '@baserow/modules/core/utils/dom'

/**
 * helper function to extract options from element
 *
 * If binding provides .arg, the .arg property should be an object:
 *
 * {duration: Number, contentIsHtml: Bool, contentClasses: String}
 *
 * @param el
 * @param binding directive binding value
 * @returns {{duration: number, contentClasses: (*|null), value, contentType: (*|string)}}
 */
const getOptions = (el, binding) => {
  // defaults
  const tooltipOptions = {
    duration: 0,
    contentIsHtml: false,
    value: null,
    contentClasses: '',
  }

  if (binding.arg && _.isObject(binding.arg)) {
    _.merge(tooltipOptions, binding.arg)
  }
  tooltipOptions.value = binding.value
  return tooltipOptions
}

// make sure only one tooltip is visible
let currentTooltip = null
const switchToTooltip = (el) => {
  if (currentTooltip != null) {
    currentTooltip.tooltipClose()
  }
  currentTooltip = el
}

/**
 * This is a very simple and fast tooltip directive. It will add the binding value as
 * tooltip content. The tooltip only shows if there is a value.
 *
 * tooltip directive can be customized with arg, where arg is an object:
 * {
 *     // duration number of seconds the tooltip should be visible after pointer
 *     // leaves i icon or tooltip content
 *  duration: Number,
 *    // contentIsHtml informs the value is html and should not be escaped (sets .innerHtml directly)
 *  contentIsHtml: Bool,
 *    // contentClasses is a string with additional css classes for tooltip content container
 *  contentClasses: String
 *  }
 *
 * <i v-tooltip:[configObject]="someValue"/>
 */
export default {
  /**
   * If there is a value and the tooltip has not yet been initialized we can add the
   * mouse events to show and hide the tooltip.
   *
   */

  initialize(el, binding) {
    el.tooltipOptions = getOptions(el, binding)
    el.onClickOutsideCallback = null

    el.updatePositionEvent = (event) => {
      const rect = el.getBoundingClientRect()
      const position = el.getAttribute('tooltip-position') || 'bottom'
      const rectTooltip = el.tooltipElement.getBoundingClientRect()

      switch (position) {
        case 'top':
          el.tooltipElement.style.top = rect.top - 2 - rectTooltip.height + 'px'
          el.tooltipElement.style.left = rect.left + rect.width / 2 + 'px'
          break
        case 'bottom-left':
          el.tooltipElement.style.top = rect.bottom + 4 + 'px'
          el.tooltipElement.style.left = rect.right - rectTooltip.width + 'px'
          el.tooltipElement.style.setProperty(
            '--tooltip-cursor-position-right',
            rect.width / 2 - 6 + 'px' // Middle of the main element
          )
          el.tooltipElement.style.setProperty(
            '--tooltip-cursor-position-left',
            'auto'
          )
          break
        case 'bottom-right':
          el.tooltipElement.style.top = rect.bottom + 4 + 'px'
          el.tooltipElement.style.left = rect.left + 'px'
          el.tooltipElement.style.setProperty(
            '--tooltip-cursor-position-left',
            rect.width / 2 + 'px' // Middle of the main element
          )
          el.tooltipElement.style.setProperty(
            '--tooltip-cursor-position-right',
            'auto'
          )
          break
        case 'bottom-cursor':
          el.tooltipElement.style.top = rect.bottom + 4 + 'px'
          el.tooltipElement.style.left =
            Math.max(
              rect.left + 6,
              Math.min(rect.left + rect.width - 6, event.x)
            ) -
            rectTooltip.width / 2 +
            'px'
          break
        default:
          el.tooltipElement.style.top = rect.bottom + 4 + 'px'
          el.tooltipElement.style.left = rect.left + rect.width / 2 + 'px'
      }
    }
    el.removeTimeout = () => {
      if (el.tooltipTimeout) {
        clearTimeout(el.tooltipTimeout)
      }
      el.tooltipTimeout = null
    }

    el.tooltipMouseMoveEvent = (event) => {
      const position = el.getAttribute('tooltip-position') || 'bottom'
      if (position === 'bottom-cursor' && el.tooltipElement) {
        el.updatePositionEvent(event)
      }
    }

    el.tooltipMouseEnterEvent = (event) => {
      switchToTooltip(el)
      const position = el.getAttribute('tooltip-position') || 'bottom'
      const hide = el.getAttribute('hide-tooltip')

      if (hide) {
        return
      }

      if (!el.tooltipElement) {
        el.tooltipElement = document.createElement('div')

        const classes = ['tooltip', 'tooltip--body']
        if (position === 'top') {
          classes.push('tooltip--top')
        }

        if (position === 'top' || position === 'bottom') {
          classes.push('tooltip--center')
        }

        el.tooltipElement.className = classes.join(' ')
        document.body.insertBefore(el.tooltipElement, document.body.firstChild)

        el.tooltipContentElement = document.createElement('div')

        el.tooltipElement.appendChild(el.tooltipContentElement)
      }

      if (el.tooltipOptions.contentIsHtml) {
        el.tooltipContentElement.innerHTML = el.tooltipOptions.value
      } else {
        el.tooltipContentElement.appendChild(
          document.createTextNode(el.tooltipOptions.value)
        )
      }

      let contentClasses = ['tooltip__content']
      if (el.tooltipOptions.contentClasses) {
        contentClasses = contentClasses.concat(el.tooltipOptions.contentClasses)
      }
      el.tooltipContentElement.className = contentClasses.join(' ')

      el.updatePositionEvent(event)
      // we just entered, so we don't want any previously set timeout to close
      // the tooltip content
      el.removeTimeout()

      // make tooltip content preserved if pointer hovers
      el.tooltipContentElement.addEventListener('mouseenter', el.removeTimeout)
      el.tooltipContentElement.addEventListener(
        'mouseleave',
        el.tooltipMoveLeaveEvent
      )

      window.addEventListener('mousemove', el.tooltipMouseMoveEvent)

      // When the user scrolls or resizes the window it could be possible that the
      // element where the tooltip is anchored to has moved, so then the position
      // needs to be updated. We only want to do this when the tooltip is visible.
      window.addEventListener('scroll', el.updatePositionEvent, true)
      window.addEventListener('resize', el.updatePositionEvent)

      // refresh the callback - old callback should be removed because old instance
      // is may be longer present, and window object may still have click event handlers
      // that check if the pointer is in or out of tooltip content element (which itself
      // is long time gone)
      el.removeTooltipOutsideClickCallback()
      el.onClickOutsideCallback = onClickOutside(
        el.tooltipContentElement,
        el.tooltipClose
      )
    }
    /**
     * queue a close tooltip action.
     *
     * This can be called multiple times. Each call will postpone tooltipClose() call.
     * This way user can hover in and hover out several times and the tooltip still be
     * visible, if duration is > 0.
     */
    el.tooltipMoveLeaveEvent = () => {
      // we should remove any pending timeout before setting new one, because timeout
      // should be counted from the last mouse leave event.
      el.removeTimeout()
      el.tooltipTimeout = setTimeout(
        el.tooltipClose,
        // timeout from caller is in seconds. remember to convert to mseconds
        el.tooltipOptions.duration * 1000
      )
    }
    el.removeTooltipOutsideClickCallback = () => {
      if (el.onClickOutsideCallback) {
        el.onClickOutsideCallback()
        el.onClickOutsideCallback = null
      }
    }
    /**
     * actually closing the tooltip here
     */
    el.tooltipClose = () => {
      // cleanup actions: remove window handlers set with onClickOutside()
      el.removeTooltipOutsideClickCallback()

      if (el.tooltipElement) {
        el.tooltipElement.parentNode.removeChild(el.tooltipElement)
        el.tooltipElement = null
        el.tooltipContentElement = null
      }

      window.removeEventListener('mousemove', el.tooltipMouseMoveEvent)
      window.removeEventListener('scroll', el.updatePositionEvent, true)
      window.removeEventListener('resize', el.updatePositionEvent)
      el.removeTimeout()
    }
    // those event listeners should be bind all the time to the el element
    el.addEventListener('mouseenter', el.tooltipMouseEnterEvent)
    el.addEventListener('mouseleave', el.tooltipMoveLeaveEvent)
  },

  /**
   * If there isn't a value or if the directive is unbinded the tooltipElement can
   * be destroyed if it wasn't already and all the events can be removed.
   */
  terminate(el) {
    if (el.tooltipElement && el.tooltipElement.parentNode) {
      el.tooltipElement.parentNode.removeChild(el.tooltipElement)
    }
    el.tooltipElement = null
    el.tooltipContentElement = null
    el.removeEventListener('mouseenter', el.tooltipMouseEnterEvent)
    el.removeEventListener('mouseleave', el.tooltipMoveLeaveEvent)
    window.removeEventListener('scroll', el.updatePositionEvent, true)
    window.removeEventListener('resize', el.updatePositionEvent)
  },
  bind(el, binding) {
    el.tooltipElement = null
    el.tooltipContentElement = null
    binding.def.update(el, binding)
  },
  update(el, binding) {
    const { value } = binding

    if (!!value && el.tooltipElement) {
      el.tooltipOptions = getOptions(el, binding)
    } else if (!!value && el.tooltipElement === null) {
      binding.def.initialize(el, binding)
    } else if (!value) {
      binding.def.terminate(el)
    }
  },
  unbind(el, binding) {
    binding.def.terminate(el)
  },
}

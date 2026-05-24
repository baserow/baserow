import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from 'prosemirror-state'

const functionHelpTooltipKey = new PluginKey('functionHelpTooltip')

export const FunctionHelpTooltipExtension = Extension.create({
  name: 'functionHelpTooltip',

  addOptions() {
    return {
      functionDefinitions: {},
      selector: '.function-formula-component',
      showDelay: 120,
      hideDelay: 60,
      onShowTooltip: null,
      onHideTooltip: null,
    }
  },

  addProseMirrorPlugins() {
    const {
      functionDefinitions,
      selector,
      showDelay,
      hideDelay,
      onShowTooltip,
      onHideTooltip,
    } = this.options
    let lastEl = null
    let lastName = null
    let showTimer = null
    let hideTimer = null
    // Element the user just clicked on. While the mouse stays on this
    // element we suppress the hover tooltip, so small cursor movements
    // after a click don't make it reappear. Cleared as soon as the mouse
    // moves to a different element or leaves the editor.
    let suppressedEl = null

    const findFunctionNodeByName = (name) => {
      const needle = (name || '').toLowerCase()
      return functionDefinitions[needle] || null
    }

    const showTooltip = (el, fname) => {
      clearTimeout(hideTimer)
      clearTimeout(showTimer)
      showTimer = setTimeout(() => {
        const node = findFunctionNodeByName(fname)
        if (!node) return
        onShowTooltip?.(el, node)
        lastEl = el
        lastName = fname
      }, showDelay)
    }

    const hideTooltip = () => {
      clearTimeout(showTimer)
      clearTimeout(hideTimer)
      hideTimer = setTimeout(() => {
        onHideTooltip?.()
        lastEl = null
        lastName = null
      }, hideDelay)
    }

    const hideTooltipImmediately = () => {
      clearTimeout(showTimer)
      clearTimeout(hideTimer)
      if (lastEl || showTimer) {
        onHideTooltip?.()
      }
      lastEl = null
      lastName = null
    }

    return [
      new Plugin({
        key: functionHelpTooltipKey,
        view(view) {
          // `mousedown` events originating inside a Vue `NodeView` with
          // `selectable: false` never reach `handleDOMEvents` because
          // TipTap's default `stopEvent` returns true for them. We attach a
          // native listener on `view.dom` (capture phase) so we reliably
          // hide the tooltip whenever the user clicks anywhere inside the
          // editor, including on a highlighted function.
          const onMouseDown = (event) => {
            hideTooltipImmediately()
            const el = event.target?.closest?.(selector)
            suppressedEl = el && view.dom.contains(el) ? el : null
          }
          view.dom.addEventListener('mousedown', onMouseDown, true)

          return {
            destroy() {
              view.dom.removeEventListener('mousedown', onMouseDown, true)
              hideTooltipImmediately()
              suppressedEl = null
            },
          }
        },
        props: {
          handleDOMEvents: {
            mousemove(view, event) {
              const root = view.dom
              const el = event.target?.closest?.(selector)
              // Release suppression once the mouse moves to a different
              // element (or outside the selector altogether).
              if (suppressedEl && el !== suppressedEl) {
                suppressedEl = null
              }
              if (el && root.contains(el)) {
                if (el === suppressedEl) return false
                const text = (el.textContent || '').trim()
                const m = text.match(/^([A-Za-z_][A-Za-z0-9_]*)/)
                const fname = m ? m[1] : null
                if (!fname) return false
                if (lastEl === el && lastName === fname) return false
                showTooltip(el, fname)
              } else if (lastEl) {
                hideTooltip()
              }
              return false
            },
            mouseleave() {
              suppressedEl = null
              if (lastEl) hideTooltip()
              return false
            },
          },
        },
      }),
    ]
  },
})

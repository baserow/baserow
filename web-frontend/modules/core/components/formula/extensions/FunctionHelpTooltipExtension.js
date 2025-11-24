import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from 'prosemirror-state'

const functionHelpTooltipKey = new PluginKey('functionHelpTooltip')

export const FunctionHelpTooltipExtension = Extension.create({
  name: 'functionHelpTooltip',

  addOptions() {
    return {
      vueComponent: null,
      functionDefinitions: {},
      selector: '.function-name-highlight',
      showDelay: 120,
      hideDelay: 60,
    }
  },

  addProseMirrorPlugins() {
    const {
      vueComponent,
      functionDefinitions,
      selector,
      showDelay,
      hideDelay,
    } = this.options
    let lastEl = null
    let lastName = null
    let showTimer = null
    let hideTimer = null

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
        vueComponent.hoveredFunctionNode = node
        vueComponent.$refs.nodeHelpTooltip?.show(el, 'bottom', 'right', 6, 10)
        lastEl = el
        lastName = fname
      }, showDelay)
    }

    const hideTooltip = () => {
      clearTimeout(showTimer)
      clearTimeout(hideTimer)
      hideTimer = setTimeout(() => {
        vueComponent.$refs.nodeHelpTooltip?.hide()
        vueComponent.hoveredFunctionNode = null
        lastEl = null
        lastName = null
      }, hideDelay)
    }

    return [
      new Plugin({
        key: functionHelpTooltipKey,
        props: {
          handleDOMEvents: {
            mousemove(view, event) {
              const root = view.dom
              const el = event.target?.closest?.(selector)
              if (el && root.contains(el)) {
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
              if (lastEl) hideTooltip()
              return false
            },
          },
        },
      }),
    ]
  },
})

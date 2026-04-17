import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { onClickOutside, isElement } from '@baserow/modules/core/utils/dom'

const contextManagementPluginKey = new PluginKey('contextManagement')

/**
 * @name ContextManagementExtension
 * @description Manages the visibility and positioning of the formula input's
 * explorer context menu (data explorer and function list). It handles focus and blur
 * events to show or hide that menu, and repositions it when the document changes.
 *
 * Validation error UI is owned by the Vue host, not this extension.
 *
 * This extension is fully decoupled from Vue: it interacts with the host
 * component exclusively through the callback/accessor options listed below.
 */
export const ContextManagementExtension = Extension.create({
  name: 'contextManagement',

  addOptions() {
    return {
      // State accessors — return current reactive values from the host.
      getState: () => ({
        isFocused: false,
        disabled: false,
        readOnly: false,
      }),
      setFocused: (_val) => {},

      // DOM element accessors for click-outside detection.
      getRootEl: () => null,
      getContextEl: () => null,

      // Explorer context menu — the host decides positioning.
      showExplorerContextMenu: () => {},
      hideContextMenu: () => {},
    }
  },

  addStorage() {
    return {
      ignoreNextBlur: false,
      clickOutsideEventCancel: null,
    }
  },

  addCommands() {
    return {
      repositionContext:
        () =>
        ({ editor }) => {
          const { isFocused } = this.options.getState()
          if (!isFocused) return false

          this.options.showExplorerContextMenu()
          return true
        },
      showContext:
        () =>
        ({ editor }) => {
          const { disabled, readOnly } = this.options.getState()
          if (readOnly || disabled) return false

          this.options.setFocused(true)

          editor.commands.unselectNode()
          this.options.showExplorerContextMenu()

          const rootEl = this.options.getRootEl()
          if (rootEl) {
            this.storage.clickOutsideEventCancel = onClickOutside(
              rootEl,
              (target, _event) => {
                const contextEl = this.options.getContextEl()
                if (!contextEl || !isElement(contextEl, target)) {
                  editor.commands.hideContext()
                }
              }
            )
          }

          return true
        },
      hideContext:
        () =>
        ({ editor }) => {
          this.options.setFocused(false)
          this.options.hideContextMenu()

          editor.commands.unselectNode()

          if (this.storage.clickOutsideEventCancel) {
            this.storage.clickOutsideEventCancel()
            this.storage.clickOutsideEventCancel = null
          }

          return true
        },

      handleContextMouseDown: () => () => {
        this.storage.ignoreNextBlur = true
        return true
      },
    }
  },

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: contextManagementPluginKey,
        props: {
          handleDOMEvents: {
            focus: (_view, _event) => {
              const { disabled, readOnly } = this.options.getState()
              if (!disabled && !readOnly) {
                this.editor.commands.showContext()
              }
              return false
            },
            blur: (_view, _event) => {
              if (this.storage.ignoreNextBlur) {
                this.storage.ignoreNextBlur = false
                return false
              }
              this.editor.commands.hideContext()
              return false
            },
          },
        },
        view: () => ({
          update: (view, prevState) => {
            const { isFocused } = this.options.getState()
            if (isFocused && view.state.doc !== prevState.doc) {
              this.editor.commands.repositionContext()
            }
          },
        }),
      }),
    ]
  },

  onCreate() {
    this.storage.ignoreNextBlur = false
    this.storage.clickOutsideEventCancel = null
  },

  onDestroy() {
    if (this.storage.clickOutsideEventCancel) {
      this.storage.clickOutsideEventCancel()
      this.storage.clickOutsideEventCancel = null
    }
  },
})

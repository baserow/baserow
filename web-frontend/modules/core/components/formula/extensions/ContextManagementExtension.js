import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'

const contextManagementPluginKey = new PluginKey('contextManagement')

/**
 * @name ContextManagementExtension
 * @description Manages the visibility and positioning of the formula input's
 * context menu (the data explorer and function list). It handles focus and blur
 * events to automatically show or hide the context menu. It also provides commands
 * to control the menu programmatically and reposition it based on the surrounding UI.
 */
export const ContextManagementExtension = Extension.create({
  name: 'contextManagement',

  addOptions() {
    return {
      vueComponent: null,
      contextPosition: 'bottom', // 'bottom', 'left', 'right'
      disabled: false,
      readOnly: false,
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
          const { vueComponent } = this.options

          if (!vueComponent || !vueComponent.isFocused) {
            return false
          }

          if (vueComponent && vueComponent.$nextTick) {
            vueComponent.$nextTick(() => {
              if (!vueComponent.isFocused) return

              // Read directly from Vue component to get reactive value
              const contextPosition =
                vueComponent?.contextPosition ?? this.options.contextPosition
              let config

              switch (contextPosition) {
                case 'left':
                  config = {
                    vertical: 'bottom',
                    horizontal: 'left',
                    needsDynamicOffset: true,
                  }
                  break
                case 'bottom':
                  config = {
                    vertical: 'bottom',
                    horizontal: 'left',
                    verticalOffset: 10,
                    horizontalOffset: 0,
                  }
                  break
                case 'right':
                  config = {
                    vertical: 'bottom',
                    horizontal: 'left',
                    needsDynamicOffset: true,
                  }
                  break
                default:
                  config = {
                    vertical: 'bottom',
                    horizontal: 'left',
                    verticalOffset: 0,
                    horizontalOffset: -400,
                  }
              }

              const { vertical, horizontal } = config
              let { verticalOffset = 0, horizontalOffset = 0 } = config

              // Calculate dynamic offsets if necessary
              if (config.needsDynamicOffset) {
                const inputRect = vueComponent.$el?.getBoundingClientRect()
                const contextRect =
                  vueComponent.$refs?.formulaInputContext?.$el?.getBoundingClientRect()

                switch (contextPosition) {
                  case 'left':
                    verticalOffset = -inputRect?.height || 0
                    horizontalOffset = -(contextRect?.width || 0) - 10
                    break
                  case 'right':
                    verticalOffset = -inputRect?.height || 0
                    horizontalOffset = (inputRect?.width || 0) + 10
                    break
                }
              }

              if (vueComponent.$refs?.formulaInputContext) {
                vueComponent.$refs.formulaInputContext.show(
                  vueComponent.$refs.editor.$el,
                  vertical,
                  horizontal,
                  verticalOffset,
                  horizontalOffset
                )
              }
            })
          }

          return true
        },
      showContext:
        () =>
        ({ editor }) => {
          const { vueComponent } = this.options

          // Read directly from Vue component to get reactive values
          const disabled = vueComponent?.disabled ?? this.options.disabled
          const readOnly = vueComponent?.readOnly ?? this.options.readOnly

          if (!vueComponent || readOnly || disabled) {
            return false
          }

          vueComponent.isFocused = true

          if (vueComponent && vueComponent.$nextTick) {
            vueComponent.$nextTick(() => {
              if (!vueComponent.isFocused) return

              editor.commands.unselectNode()

              // Position the context
              editor.commands.repositionContext()

              if (vueComponent && vueComponent.$el) {
                const {
                  onClickOutside,
                  isElement,
                } = require('@baserow/modules/core/utils/dom')

                this.storage.clickOutsideEventCancel = onClickOutside(
                  vueComponent.$el,
                  (target, event) => {
                    if (
                      vueComponent.$refs?.formulaInputContext &&
                      !isElement(
                        vueComponent.$refs.formulaInputContext.$el,
                        target
                      )
                    ) {
                      editor.commands.hideContext()
                    }
                  }
                )
              }
            })
          }

          return true
        },
      hideContext:
        () =>
        ({ editor }) => {
          const { vueComponent } = this.options

          if (vueComponent) {
            vueComponent.isFocused = false
          }

          if (vueComponent?.$refs?.formulaInputContext) {
            vueComponent.$refs.formulaInputContext.hide()
          }

          editor.commands.unselectNode()

          if (this.storage.clickOutsideEventCancel) {
            this.storage.clickOutsideEventCancel()
            this.storage.clickOutsideEventCancel = null
          }

          return true
        },

      handleDataExplorerMouseDown: () => () => {
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
            focus: (view, event) => {
              if (!this.options.disabled && !this.options.readOnly) {
                this.editor.commands.showContext()
              }
              return false
            },
            blur: (view, event) => {
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
            // Reposition context when the document changes and context is visible
            const { vueComponent } = this.options
            if (vueComponent?.isFocused && view.state.doc !== prevState.doc) {
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
    // Clean up listeners
    if (this.storage.clickOutsideEventCancel) {
      this.storage.clickOutsideEventCancel()
      this.storage.clickOutsideEventCancel = null
    }
  },
})

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
      isFocused: false,
      ignoreNextBlur: false,
      clickOutsideEventCancel: null,
    }
  },

  addCommands() {
    return {
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

          this.storage.isFocused = true

          if (vueComponent) {
            vueComponent.isFocused = true
          }

          if (vueComponent && vueComponent.$nextTick) {
            vueComponent.$nextTick(() => {
              if (!this.storage.isFocused) return

              editor.commands.unselectNode()

              // Read directly from Vue component to get reactive value
              const contextPosition =
                vueComponent?.contextPosition ?? this.options.contextPosition
              let config

              switch (contextPosition) {
                case 'left':
                  config = {
                    vertical: 'top',
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
                    vertical: 'top',
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

          this.storage.isFocused = false

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
      }),
    ]
  },

  onCreate() {
    this.storage.isFocused = false
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

  scheduleContextDisplay() {
    const { vueComponent } = this.options

    if (!vueComponent || !this.storage.isFocused) {
      return
    }

    vueComponent.$nextTick(() => {
      if (!this.storage.isFocused) return

      this.editor.commands.unselectNode()

      const config = this.getContextConfig()
      const { vertical, horizontal } = config
      let { verticalOffset = 0, horizontalOffset = 0 } = config

      if (config.needsDynamicOffset) {
        const offsets = this.calculateDynamicOffsets()
        verticalOffset = offsets.verticalOffset
        horizontalOffset = offsets.horizontalOffset
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

      this.setupClickOutsideListener()
    })
  },

  getContextConfig() {
    const { vueComponent } = this.options
    // Read directly from Vue component to get reactive value
    const contextPosition =
      vueComponent?.contextPosition ?? this.options.contextPosition

    switch (contextPosition) {
      case 'left':
        return {
          vertical: 'top',
          horizontal: 'left',
          needsDynamicOffset: true,
        }
      case 'bottom':
        return {
          vertical: 'bottom',
          horizontal: 'left',
          verticalOffset: 10,
          horizontalOffset: 0,
        }
      case 'right':
        return {
          vertical: 'top',
          horizontal: 'left',
          needsDynamicOffset: true,
        }
      default:
        return {
          vertical: 'bottom',
          horizontal: 'left',
          verticalOffset: 0,
          horizontalOffset: -400,
        }
    }
  },

  calculateDynamicOffsets() {
    const { vueComponent } = this.options

    if (!vueComponent) {
      return { verticalOffset: 0, horizontalOffset: 0 }
    }

    // Read directly from Vue component to get reactive value
    const contextPosition =
      vueComponent?.contextPosition ?? this.options.contextPosition

    // Calculate dynamic offsets based on position and dimensions
    const inputRect = vueComponent.$el?.getBoundingClientRect()
    const contextRect =
      vueComponent.$refs?.formulaInputContext?.$el?.getBoundingClientRect()

    switch (contextPosition) {
      case 'left':
        return {
          verticalOffset: -inputRect?.height || 0,
          horizontalOffset: -(contextRect?.width || 0) - 10,
        }
      case 'right':
        return {
          verticalOffset: -inputRect?.height || 0,
          horizontalOffset: (inputRect?.width || 0) + 10,
        }
      default:
        return {
          verticalOffset: 0,
          horizontalOffset: 0,
        }
    }
  },

  setupClickOutsideListener() {
    const { vueComponent } = this.options

    if (!vueComponent || !vueComponent.$el) {
      return
    }

    const {
      onClickOutside,
      isElement,
    } = require('@baserow/modules/core/utils/dom')

    this.storage.clickOutsideEventCancel = onClickOutside(
      vueComponent.$el,
      (target, event) => {
        if (
          vueComponent.$refs?.formulaInputContext &&
          !isElement(vueComponent.$refs.formulaInputContext.$el, target)
        ) {
          this.editor.commands.hideContext()
        }
      }
    )
  },
})

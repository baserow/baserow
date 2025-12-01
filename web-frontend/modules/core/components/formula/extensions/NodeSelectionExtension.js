import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'

const nodeSelectionPluginKey = new PluginKey('nodeSelection')

/**
 * @name NodeSelectionExtension
 * @description A Tiptap extension for managing the selection of special "data
 * component" nodes within the formula editor. These nodes represent non-textual
 * elements like field references (e.g., `get('field', 'name')`).
 */
export const NodeSelectionExtension = Extension.create({
  name: 'nodeSelection',

  addOptions() {
    return {
      vueComponent: null,
    }
  },

  addStorage() {
    return {
      selectedNode: null,
    }
  },

  addCommands() {
    return {
      selectNode:
        (node) =>
        ({ editor }) => {
          if (node) {
            editor.commands.unselectNode()

            this.storage.selectedNode = node
            this.storage.selectedNode.attrs.isSelected = true

            const { vueComponent } = this.options
            if (vueComponent) {
              vueComponent.$emit('node-selected', {
                node: this.storage.selectedNode,
                path: this.storage.selectedNode.attrs?.path || null,
              })
            }
          }

          return true
        },
      unselectNode:
        () =>
        ({ editor }) => {
          if (this.storage.selectedNode) {
            this.storage.selectedNode.attrs.isSelected = false

            const { vueComponent } = this.options
            if (vueComponent) {
              vueComponent.$emit('node-unselected', {
                node: this.storage.selectedNode,
              })
            }

            this.storage.selectedNode = null
          }

          return true
        },
      getSelectedNode: () => () => {
        return this.storage.selectedNode
      },
      getSelectedNodePath: () => () => {
        return this.storage.selectedNode?.attrs?.path || null
      },
    }
  },

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: nodeSelectionPluginKey,
        props: {
          handleClick: (view, pos, event) => {
            const { target } = event

            const isDataComponent =
              target.closest('[data-type="get-formula-component"]') ||
              target.hasAttribute('data-node-clicked')

            if (!isDataComponent) {
              this.editor.commands.unselectNode()
            }

            // Return false to allow default click handling
            return false
          },
        },
      }),
    ]
  },

  onCreate() {
    this.editor.on('update', () => {
      this.editor.commands.unselectNode()
    })
  },

  onDestroy() {
    if (this.storage.selectedNode) {
      this.storage.selectedNode.attrs.isSelected = false
      this.storage.selectedNode = null
    }
  },
})

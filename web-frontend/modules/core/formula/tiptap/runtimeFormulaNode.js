import { defineAsyncComponent } from 'vue'
import { Node, VueNodeViewRenderer } from '@tiptap/vue-3'
import { mergeAttributes } from '@tiptap/core'

export function createRuntimeFormulaNode(runtimeFormulaFunction) {
  const loader = runtimeFormulaFunction.formulaComponentLoader
  if (loader === null) {
    return null
  }
  const formulaComponentType = runtimeFormulaFunction.formulaComponentType
  const component = defineAsyncComponent(loader)
  return Node.create({
    name: formulaComponentType,
    group: 'inline',
    inline: true,
    selectable: false,
    atom: true,
    addNodeView() {
      return VueNodeViewRenderer(component)
    },
    addAttributes() {
      return {
        path: {
          default: '',
        },
        isSelected: {
          default: false,
        },
      }
    },
    parseHTML() {
      return [
        {
          tag: formulaComponentType,
        },
      ]
    },
    renderHTML({ HTMLAttributes }) {
      return [formulaComponentType, mergeAttributes(HTMLAttributes)]
    },
  })
}

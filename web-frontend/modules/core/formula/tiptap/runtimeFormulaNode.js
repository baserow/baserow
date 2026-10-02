import { Node, VueNodeViewRenderer } from '@tiptap/vue-3'
import { mergeAttributes } from '@tiptap/core'
import GetFormulaComponent from '@baserow/modules/core/components/formula/GetFormulaComponent'
import { RuntimeGet } from '@baserow/modules/core/runtimeFormulaTypes'

export function createRuntimeFormulaNode(runtimeFormulaFunction) {
  return runtimeFormulaFunction.formulaComponent
}

function createRuntimeGetFormulaNode(runtimeFormulaFunction) {
  const formulaComponentType = runtimeFormulaFunction.formulaComponentType
  return Node.create({
    name: formulaComponentType,
    group: 'inline',
    inline: true,
    selectable: false,
    atom: true,
    addNodeView() {
      // TipTap reads NodeViewWrapper's DOM synchronously during construction.
      return VueNodeViewRenderer(GetFormulaComponent)
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

// Preserve the original getter contract, including subclasses that extend
// super.formulaComponent, without loading editor UI from the runtime registry.
RuntimeGet.registerFormulaComponentFactory(createRuntimeGetFormulaNode)

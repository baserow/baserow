import { RuntimeGet } from '@baserow/modules/core/runtimeFormulaTypes'
import { Node, VueNodeViewRenderer } from '@tiptap/vue-3'
import { mergeAttributes } from '@tiptap/core'
import GetFormulaComponent from '@baserow/modules/core/components/formula/GetFormulaComponent'

/** The editor node is registered only by the application shell. */
export class RuntimeGetEditor extends RuntimeGet {
  get formulaComponent() {
    const formulaComponentType = this.formulaComponentType
    return Node.create({
      name: formulaComponentType,
      group: 'inline',
      inline: true,
      selectable: false,
      atom: true,
      addNodeView() {
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
}

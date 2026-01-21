import { VueRenderer } from '@tiptap/vue-3'
import tippy from 'tippy.js'

import RichTextEditorMentionsList from '@baserow/modules/core/components/editor/RichTextEditorMentionsList'

export default ({ users }) => ({
  render: () => {
    let popup
    let component

    return {
      onStart: (props) => {
        component = new VueRenderer(RichTextEditorMentionsList, {
          editor: props.editor,
          props: { users, ...props },
        })

        if (!props.clientRect) {
          return
        }

        popup = tippy('body', {
          getReferenceClientRect: props.clientRect,
          appendTo: () => document.body,
          content: component.element,
          showOnCreate: true,
          interactive: true,
          trigger: 'manual',
          placement: 'top-start',
          offset: [0, 5],
        })
      },

      onUpdate(props) {
        component.updateProps(props)

        if (!props.clientRect) {
          return
        }

        popup[0].setProps({
          getReferenceClientRect: props.clientRect,
        })
      },

      onKeyDown(props) {
        if (props.event.key === 'Escape') {
          popup[0].hide()

          return true
        }

        return component.ref?.onKeyDown(props)
      },

      onExit() {
        if (component) {
          popup[0].destroy()
          component.destroy()
        }
      },
    }
  },
})

import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'

export const TextSegmentWrapperExtension = Extension.create({
  name: 'textSegmentWrapper',

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('textSegmentWrapper'),
        // This plugin runs after FunctionDetectionExtension
        // If FunctionDetection handles the input, it returns true and this plugin won't run
        props: {
          handleTextInput(view, from, to, text) {
            const { state, dispatch } = view
            const { schema, tr } = state

            // Don't wrap if typing comma, closing paren, or opening paren
            // These should be handled by FunctionDetectionExtension first
            if (text === ',' || text === ')' || text === '(') {
              return false
            }

            // Check if we're inside an existing text-segment
            const $from = state.doc.resolve(from)
            let insideTextSegment = false

            for (let i = $from.depth; i > 0; i--) {
              const node = $from.node(i)
              if (node.type.name === 'text-segment') {
                insideTextSegment = true
                break
              }
            }

            // If we're already inside a text-segment
            if (insideTextSegment) {
              // Check if the text-segment only contains a zero-width space
              const parentNode = $from.parent
              if (parentNode.textContent === '\u200B') {
                // Replace the zero-width space with the typed text
                const segmentStart = $from.before($from.depth)
                const segmentEnd = segmentStart + parentNode.nodeSize

                const newTextSegment = schema.nodes['text-segment'].create(
                  null,
                  schema.text(text)
                )

                tr.replaceWith(segmentStart, segmentEnd, newTextSegment)

                // Position cursor after the typed text
                const cursorPos = segmentStart + 1 + text.length
                tr.setSelection(
                  state.selection.constructor.near(tr.doc.resolve(cursorPos))
                )

                dispatch(tr)
                return true
              }

              // Otherwise let default behavior handle it
              return false
            }

            // Create a text-segment node containing the text
            const textSegmentNode = schema.nodes['text-segment'].create(
              null,
              schema.text(text)
            )

            // Insert the text-segment node
            tr.replaceWith(from, to, textSegmentNode)

            // Position cursor after the inserted text
            const cursorPos = from + 1 + text.length
            tr.setSelection(
              state.selection.constructor.near(tr.doc.resolve(cursorPos))
            )

            dispatch(tr)
            return true
          },
        },
      }),
    ]
  },
})

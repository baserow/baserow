import { Extension } from '@tiptap/core'

export function getCodeAutoIndentText(textBeforeCursor, indent) {
  const currentLine = textBeforeCursor.split('\n').pop() || ''
  const currentIndent = currentLine.match(/^[\t ]*/)?.[0] || ''
  const shouldIndentNextLine = /[{[(]\s*$/.test(currentLine)

  return `\n${currentIndent}${shouldIndentNextLine ? indent : ''}`
}

export const CodeAutoIndentExtension = Extension.create({
  name: 'codeAutoIndent',
  priority: 1000,

  addOptions() {
    return {
      indent: '  ',
    }
  },

  addKeyboardShortcuts() {
    return {
      Enter: () => {
        const { state } = this.editor
        const { selection } = state
        const { $from } = selection

        if ($from.parent.type.name !== 'codeBlock') {
          return false
        }

        const textBeforeCursor = $from.parent.textBetween(
          0,
          $from.parentOffset,
          '\n',
          '\n'
        )
        const indentation = getCodeAutoIndentText(
          textBeforeCursor,
          this.options.indent
        )

        return this.editor.commands.insertContent(indentation, {
          parseOptions: {
            preserveWhitespace: 'full',
          },
        })
      },
    }
  },
})

export default CodeAutoIndentExtension

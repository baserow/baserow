<template>
  <div class="code-editor">
    <EditorContent :editor="editor" />
  </div>
</template>

<script>
import { Editor, EditorContent } from '@tiptap/vue-3'

import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'

const CodeEditorDocument = Document.extend({
  content: 'codeBlock',
})

export default {
  name: 'CodeEditor',
  components: {
    EditorContent,
  },
  props: {
    language: {
      type: String,
      default: 'javascript',
      validator: (value) => ['javascript', 'css'].includes(value),
    },
    modelValue: {
      type: String,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  data() {
    return {
      editor: null,
    }
  },
  watch: {
    modelValue(newCode) {
      if (this.editor && newCode !== this.getCurrentCode()) {
        this.editor.commands.setContent(
          this.generateCodeBlock(newCode),
          false,
          {
            preserveWhitespace: 'full',
          }
        )
      }
    },
    language() {
      if (this.editor) {
        this.editor.commands.setContent(
          this.generateCodeBlock(this.getCurrentCode()),
          false,
          {
            preserveWhitespace: 'full',
          }
        )
      }
    },
  },
  async mounted() {
    const { CodeBlockLowlight } =
      await import('@tiptap/extension-code-block-lowlight')
    const { createLowlight } = await import('lowlight')
    const lowlight = createLowlight()

    const { default: javascript } =
      await import('highlight.js/lib/languages/javascript')
    const { default: css } = await import('highlight.js/lib/languages/css')

    lowlight.register('javascript', javascript)
    lowlight.register('css', css)

    const LockedCodeBlockLowlight = CodeBlockLowlight.extend({
      addKeyboardShortcuts() {
        const parentShortcuts = this.parent?.() || {}

        return {
          ...parentShortcuts,
          Backspace: () => {
            const { empty, $anchor } = this.editor.state.selection

            if (!empty || $anchor.parent.type.name !== this.name) {
              return false
            }

            if ($anchor.pos === 1 || !$anchor.parent.textContent.length) {
              return true
            }

            return false
          },
        }
      },
    })

    this.editor = new Editor({
      extensions: [
        CodeEditorDocument,
        Text,
        LockedCodeBlockLowlight.configure({
          lowlight,
          exitOnTripleEnter: false,
          exitOnArrowDown: false,
          HTMLAttributes: {
            class: 'code-editor__code-wrapper',
          },
        }),
      ],
      content: this.generateCodeBlock(this.modelValue),
      onUpdate: () => {
        this.$emit('update:modelValue', this.getCurrentCode())
      },
    })
  },
  beforeUnmount() {
    this.editor?.destroy()
  },
  methods: {
    generateCodeBlock(code) {
      return {
        type: 'doc',
        content: [
          {
            type: 'codeBlock',
            attrs: {
              language: this.language,
            },
            content: code ? [{ type: 'text', text: code }] : [],
          },
        ],
      }
    },
    getCurrentCode() {
      return this.editor?.getText() || ''
    },
  },
}
</script>

<template>
  <div class="code-editor">
    <EditorContent :editor="editor" />
  </div>
</template>

<script>
import { Editor, EditorContent } from '@tiptap/vue-3'

import { Document } from '@tiptap/extension-document'
import { Paragraph } from '@tiptap/extension-paragraph'
import { Text } from '@tiptap/extension-text'

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
        this.editor.commands.setContent(this.generateCodeBlock(newCode))
      }
    },
    language() {
      if (this.editor) {
        this.editor.commands.setContent(
          this.generateCodeBlock(this.getCurrentCode())
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

    this.editor = new Editor({
      extensions: [
        Document,
        Paragraph,
        Text,
        CodeBlockLowlight.configure({
          lowlight,
        }),
      ],
      content: this.generateCodeBlock(this.modelValue),
      onUpdate: ({ editor }) => {
        this.$emit('update:modelValue', this.getCurrentCode())
      },
    })
  },
  beforeUnmount() {
    this.editor?.destroy()
  },
  methods: {
    generateCodeBlock(code) {
      return `<pre class="code-editor__code-wrapper"><code class="code-editor__code code-editor__code--language-${
        this.language
      }">${this.escapeHtml(code)}</code></pre>`
    },
    getCurrentCode() {
      const codeNode = this.editor?.getJSON()?.content?.[0]?.content?.[0]
      return codeNode?.text || ''
    },
    escapeHtml(string) {
      return string
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
    },
  },
}
</script>

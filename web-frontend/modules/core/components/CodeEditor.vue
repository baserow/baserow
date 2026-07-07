<template>
  <div class="code-editor__container">
    <div class="code-editor">
      <EditorContent :editor="editor" />
      <ButtonIcon
        class="code-editor__expand"
        icon="iconoir-expand"
        size="small"
        type="secondary"
        :title="modalTitle"
        :aria-label="modalTitle"
        @click="showModal"
      />
    </div>
    <Modal
      ref="modal"
      class="code-editor__modal"
      wide
      content-scrollable
      @show="focusModalEditor"
    >
      <h2 class="box__title">
        {{ modalTitle }}
      </h2>
      <div class="code-editor code-editor--modal">
        <EditorContent :editor="modalEditor" />
      </div>
    </Modal>
  </div>
</template>

<script>
import { Editor, EditorContent } from '@tiptap/vue-3'
import { Placeholder } from '@tiptap/extension-placeholder'

import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import CodeAutoIndentExtension from '@baserow/modules/core/editor/codeAutoIndentExtension'

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
    placeholder: {
      type: String,
      default: '',
    },
    modalTitle: {
      type: String,
      default: 'Code',
    },
  },
  emits: ['update:modelValue'],
  data() {
    return {
      editor: null,
      modalEditor: null,
      LockedCodeBlockLowlight: null,
      lowlight: null,
    }
  },
  watch: {
    modelValue(newCode) {
      this.setEditorContent(this.editor, newCode)
      this.setEditorContent(this.modalEditor, newCode)
    },
    language() {
      this.setEditorContent(this.editor, this.modelValue)
      this.setEditorContent(this.modalEditor, this.modelValue)
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

    this.lowlight = lowlight
    this.LockedCodeBlockLowlight = CodeBlockLowlight.extend({
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

    this.editor = this.createEditor()
    this.modalEditor = this.createEditor()
  },
  beforeUnmount() {
    this.editor?.destroy()
    this.modalEditor?.destroy()
  },
  methods: {
    createEditor() {
      return new Editor({
        extensions: [
          CodeEditorDocument,
          Text,
          Placeholder.configure({
            placeholder: this.placeholder,
          }),
          CodeAutoIndentExtension,
          this.LockedCodeBlockLowlight.configure({
            lowlight: this.lowlight,
            exitOnTripleEnter: false,
            exitOnArrowDown: false,
            HTMLAttributes: {
              class: 'code-editor__code-wrapper',
            },
          }),
        ],
        content: this.generateCodeBlock(this.modelValue),
        onUpdate: ({ editor }) => {
          const currentCode = editor.getText()
          if (this.modelValue !== currentCode) {
            this.$emit('update:modelValue', currentCode)
          }
        },
      })
    },
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
    setEditorContent(editor, code) {
      if (editor && code !== editor.getText()) {
        editor.commands.setContent(this.generateCodeBlock(code), false, {
          preserveWhitespace: 'full',
        })
      }
    },
    showModal() {
      this.$refs.modal.show()
    },
    focusModalEditor() {
      this.$nextTick(() => {
        this.modalEditor?.commands.focus('end')
      })
    },
  },
}
</script>

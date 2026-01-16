<template>
  <Modal
    ref="modal"
    :full-height="true"
    :content-padding="false"
    :right="true"
    @show="show"
    @hidden="$emit('hidden', $event)"
  >
    <template #content>
      <div class="box__title">
        <h2 class="row-modal__title">
          {{ field.name }}
        </h2>
      </div>
      <RichTextEditor
        ref="editor"
        class="rich-text-modal__editor"
        :enable-rich-text-formatting="true"
        :mentionable-users="mentionableUsers"
        :model-value="modelValue"
        @update:model-value="$emit('update:modelValue', $event)"
      ></RichTextEditor>
    </template>
  </Modal>
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'FieldRichTextModal',
  components: { RichTextEditor },
  mixins: [modal],
  props: {
    field: {
      type: Object,
      required: true,
    },
    modelValue: {
      type: [String, Object],
      required: true,
    },
    mentionableUsers: {
      type: [Array],
      default: () => [],
    },
  },
  emits: ['hidden', 'input', 'update:modelValue'],
  watch: {
    modelValue: {
      handler(value) {
        this.richCopy = value || ''
      },
      immediate: true,
    },
  },
  methods: {
    show() {
      this.$nextTick(() => {
        this.$refs.editor.focus()
      })
    },
    isOpen() {
      return this.$refs.modal.isOpen()
    },
    // Used by the parent to serialize the editor content to markdown.
    serializeToMarkdown() {
      return this.$refs.editor.serializeToMarkdown()
    },
  },
}
</script>

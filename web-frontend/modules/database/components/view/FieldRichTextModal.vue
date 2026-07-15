<template>
  <Modal
    ref="modal"
    :full-height="true"
    :content-padding="false"
    :right="true"
    :can-close="!error"
    @show="show"
    @hidden="$emit('hidden', $event)"
  >
    <template #content>
      <div class="rich-text-modal">
        <div class="box__title">
          <h2 class="row-modal__title">
            {{ field.name }}
          </h2>
        </div>
        <Alert v-if="error" type="error" class="rich-text-modal__alert">
          {{ error }}
        </Alert>
        <RichTextEditor
          ref="editor"
          class="rich-text-modal__editor"
          :enable-rich-text-formatting="true"
          :mentionable-users="mentionableUsers"
          :model-value="modelValue"
          @update:model-value="$emit('update:modelValue', $event)"
        ></RichTextEditor>
      </div>
    </template>
  </Modal>
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import Alert from '@baserow/modules/core/components/Alert'
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'FieldRichTextModal',
  components: { RichTextEditor, Alert },
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
    error: {
      type: String,
      default: null,
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
    // Editor is only mounted while open; guard for reactive validation during the transition.
    serializeToMarkdown() {
      return this.$refs.editor?.serializeToMarkdown() ?? ''
    },
  },
}
</script>

<template>
  <div class="control__elements">
    <RichTextEditor
      ref="input"
      v-model="richCopy"
      class="form-input field-rich-text"
      :class="{
        'form-input--error': touched && !isValid(),
        active: editing,
      }"
      :disabled="readOnly"
      :editable="!readOnly"
      :enable-rich-text-formatting="true"
      :mentionable-users="workspace ? workspace.users : null"
      :menu-container="getMenuContainer"
      :scrollable-area-element="getScrollableAreaElement"
      :clipboard-markdown-resolver="resolveClipboardMarkdown"
      :upload-file="readOnly ? null : uploadUserFile"
      @focus="select()"
      @blur="unselect()"
    ></RichTextEditor>

    <div v-show="touched && !isValid()" class="error">
      {{ getError() }}
    </div>
  </div>
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import UserFileService from '@baserow/modules/core/services/userFile'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import rowEditFieldInput from '@baserow/modules/database/mixins/rowEditFieldInput'
import { getRichTextClipboardContent } from '@baserow/modules/database/utils/clipboard'

export default {
  components: { RichTextEditor },
  mixins: [rowEditField, rowEditFieldInput],
  data() {
    return {
      // local copy of the value storing the JSON representation of the rich text editor
      richCopy: '',
    }
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.workspaceId)
    },
  },
  watch: {
    value: {
      handler(value) {
        this.richCopy = value || ''
      },
      immediate: true,
    },
  },
  methods: {
    resolveClipboardMarkdown: getRichTextClipboardContent,
    async uploadUserFile(file) {
      return await UserFileService(this.$client).uploadFile(file)
    },
    getError() {
      return this.getValidationError(this.$refs.input?.serializeToMarkdown())
    },
    unselect() {
      this.$super(rowEditFieldInput).unselect()
      this.editing = false
    },
    getMenuContainer() {
      // Body-level so floating-ui's fixed strategy anchors to the viewport, not a modal ancestor.
      return document.body
    },
    getScrollableAreaElement() {
      return this.$el?.closest('.modal__box-content') ?? null
    },
    beforeSave() {
      // No ref (modal teardown) or an unchanged value means nothing to reserialize.
      if (!this.$refs.input?.isDirty()) {
        return this.value
      }
      return this.$refs.input.serializeToMarkdown()
    },
  },
}
</script>

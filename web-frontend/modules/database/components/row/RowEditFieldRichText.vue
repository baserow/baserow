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
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import rowEditFieldInput from '@baserow/modules/database/mixins/rowEditFieldInput'

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
    getError() {
      return this.getValidationError(this.$refs.input?.serializeToMarkdown())
    },
    unselect() {
      this.$super(rowEditFieldInput).unselect()
      this.editing = false
    },
    beforeSave() {
      // Reserializing an untouched legacy value could rewrite it on mere blur.
      if (!this.$refs.input.isDirty()) {
        return this.value
      }
      return this.$refs.input.serializeToMarkdown()
    },
  },
}
</script>

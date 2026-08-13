<template>
  <div class="row-history-entry__field-content">
    <div v-if="entry.before[fieldIdentifier]">
      <div
        class="row-history-entry__diff row-history-entry__diff--removed row-history-entry__diff--full-width"
      >
        <RichTextEditor
          :editable="false"
          :enable-rich-text-formatting="true"
          :mentionable-users="workspace.users"
          :model-value="beforeValue"
        ></RichTextEditor>
      </div>
    </div>
    <div v-if="entry.after[fieldIdentifier]">
      <div
        class="row-history-entry__diff row-history-entry__diff--added row-history-entry__diff--full-width"
      >
        <RichTextEditor
          :editable="false"
          :enable-rich-text-formatting="true"
          :mentionable-users="workspace.users"
          :model-value="afterValue"
        ></RichTextEditor>
      </div>
    </div>
  </div>
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import { replaceImagesWithPlaceholder } from '@baserow/modules/core/editor/richTextImageUtils'

export default {
  name: 'RowHistoryFieldText',
  components: { RichTextEditor },
  props: {
    workspaceId: {
      type: Number,
      required: true,
    },
    entry: {
      type: Object,
      required: true,
    },
    fieldIdentifier: {
      type: String,
      required: true,
    },
    field: {
      type: Object,
      required: false,
      default: null,
    },
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.workspaceId)
    },
    // History serves the stored snapshot, whose image refs the editor renders as
    // literal markdown here because images are off. Show the alt text instead.
    beforeValue() {
      return replaceImagesWithPlaceholder(
        this.entry.before[this.fieldIdentifier]
      )
    },
    afterValue() {
      return replaceImagesWithPlaceholder(
        this.entry.after[this.fieldIdentifier]
      )
    },
  },
}
</script>

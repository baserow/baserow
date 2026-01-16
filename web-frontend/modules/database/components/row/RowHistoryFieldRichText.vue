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
          :model-value="entry.before[fieldIdentifier]"
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
          :model-value="entry.after[fieldIdentifier]"
        ></RichTextEditor>
      </div>
    </div>
  </div>
</template>

<script>
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'

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
  },
}
</script>

<template>
  <component
    :is="outputCardComponent"
    :row="row"
    :field="field"
    :value="value"
    :workspace-id="workspaceId"
    v-bind="richTextProps"
  />
</template>

<script>
export default {
  name: 'RowCardFieldAI',
  props: {
    row: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    value: {
      type: null,
      default: null,
    },
    workspaceId: {
      type: Number,
      required: true,
    },
  },
  computed: {
    outputCardComponent() {
      return this.$registry
        .get('aiFieldOutputType', this.field.ai_output_type)
        .getBaserowFieldType()
        .getCardComponent(this.field)
    },
    richTextProps() {
      return this.$registry
        .get('field', this.field.type)
        .hasRichTextOutput(this.field)
        ? { enableMentions: false, enableImages: false }
        : {}
    },
  },
}
</script>

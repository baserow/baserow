<template>
  <component
    :is="getFieldComponent(field.type)"
    :workspace-id="workspaceId"
    :row="row"
    :field="field"
    :value="row[`field_${field.id}`]"
    :selected="false"
    :state="{}"
    :read-only="true"
  />
</template>

<script>
export default {
  name: 'SimpleGridField',
  props: {
    field: {
      type: Object,
      required: true,
    },
    row: {
      type: Object,
      required: true,
    },
    workspaceId: {
      type: Number,
      required: false,
      default: null,
    },
  },
  methods: {
    getFieldComponent(type) {
      return this.$registry
        .get('field', type)
        .getFunctionalGridViewFieldComponent(this.field)
    },
  },
}
</script>

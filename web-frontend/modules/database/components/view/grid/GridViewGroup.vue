<template>
  <div class="grid-view__group" v-bind="$attrs">
    <div class="grid-view__group-cell">
      <div class="grid-view__group-value">
        <component :is="groupByComponent" :field="field" :value="value" />
      </div>
      <div v-if="count > 0" class="grid-view__group-count">
        {{ count }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GridViewGroup',
  props: {
    groupBy: {
      type: Object,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    value: {
      type: null,
      required: true,
    },
    count: {
      type: Number,
      required: true,
    },
  },
  computed: {
    field() {
      return this.getField(this.allFieldsInTable, this.groupBy)
    },
    groupByComponent() {
      return this.getGroupByComponent(this.field, this)
    },
  },
  methods: {
    getField(allFieldsInTable, groupBy) {
      const field = allFieldsInTable.find((f) => f.id === groupBy.field)
      return field
    },
    getGroupByComponent(field, parent) {
      const fieldType = parent.$registry.get('field', field.type)
      return fieldType.getGroupByComponent(field)
    },
  },
}
</script>

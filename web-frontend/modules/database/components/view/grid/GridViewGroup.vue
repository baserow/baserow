<template functional>
  <div class="grid-view__group" :style="[data.staticStyle, data.style]">
    <div
      class="grid-view__group-cell"
      :set="
        (field = $options.methods.getField(
          props.allFieldsInTable,
          props.groupBy
        ))
      "
    >
      <div class="grid-view__group-value">
        <component
          :is="$options.methods.getGroupByComponent(field, parent)"
          :field="field"
          :value="props.value"
        />
      </div>
      <div v-if="props.count > 0" class="grid-view__group-count">
        {{ props.count }}
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
      validator: () => true,
      required: true,
    },
    count: {
      type: Number,
      required: true,
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

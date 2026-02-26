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
    field: {
      type: Object,
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
    groupByComponent() {
      const fieldType = this.$registry.get('field', this.field.type)
      return fieldType.getGroupByComponent(this.field)
    },
  },
}
</script>

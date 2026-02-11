<template>
  <component
    :is="componentType"
    v-if="componentType"
    :row="row"
    :field="field"
    :value="value"
  ></component>
  <div v-else class="card-text">Unknown Field Type</div>
</template>

<script>
export default {
  height: 22,
  name: 'RowCardFieldFormula',
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
  },
  computed: {
    componentType() {
      if (!this.$registry) {
        return null
      }
      const formulaType = this.$registry.get(
        'formula_type',
        this.field.formula_type
      )
      return formulaType.getCardComponent(this.field)
    },
  },
}
</script>

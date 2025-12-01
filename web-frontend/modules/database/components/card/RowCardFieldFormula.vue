<template functional>
  <component
    :is="$options.methods.getComponent(props.field, parent.$registry)"
    v-if="$options.methods.getComponent(props.field, parent.$registry)"
    :row="props.row"
    :field="props.field"
    :value="props.value"
  ></component>
  <div v-else class="card-text">Unknown Field Type</div>
</template>

<script>
export default {
  height: 22,
  name: 'RowCardFieldFormula',
  components: {},
  methods: {
    getComponent(field, $registry) {
      const formulaType = $registry.get('formula_type', field.formula_type)
      return formulaType.getCardComponent(field)
    },
  },
}
</script>

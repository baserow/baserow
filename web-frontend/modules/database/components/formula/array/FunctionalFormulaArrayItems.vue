<!--
This component is used to render the formula array items, independently of the place.
It's used in the grid view cell, row edit modal, gallery card, etc.
-->
<template functional>
  <div :class="[data.staticClass, data.class]">
    <component
      :is="$options.methods.getComponent(props.field, parent.$registry)"
      v-for="(item, index) in props.value || []"
      :key="index"
      :row="props.row"
      :field="props.field"
      :value="$options.methods.getValue(props.field, parent.$registry, item)"
      :selected="props.selected"
      :index="index"
      v-on="listeners"
    ></component>
    <slot></slot>
  </div>
</template>

<script>
export default {
  name: 'FunctionalFormulaArrayItems',
  methods: {
    getComponent(field, $registry) {
      const formulaType = $registry.get(
        'formula_type',
        field.array_formula_type
      )
      return formulaType.getFunctionalFieldArrayComponent()
    },
    getValue(field, $registry, item) {
      const formulaType = $registry.get(
        'formula_type',
        field.array_formula_type
      )
      return formulaType.getItemIsInNestedValueObjectWhenInArray()
        ? item && item.value
        : item
    },
  },
}
</script>

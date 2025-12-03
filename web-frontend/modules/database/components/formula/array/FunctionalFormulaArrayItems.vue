<!--
This component is used to render the formula array items, independently of the place.
It's used in the grid view cell, row edit modal, gallery card, etc.
-->
<template>
  <div v-bind="containerAttrs">
    <component
      :is="getComponent(field, $registry)"
      v-for="(item, index) in value || []"
      :key="index"
      :row="row"
      :field="field"
      :value="getValue(field, $registry, item)"
      :selected="selected"
      :index="index"
      v-bind="listenerAttrs"
    ></component>
    <slot></slot>
  </div>
</template>

<script>
export default {
  name: 'FunctionalFormulaArrayItems',
  inheritAttrs: false,
  props: {
    field: {
      type: Object,
      required: true,
    },
    value: {
      type: Array,
      default: () => [],
    },
    row: {
      type: Object,
      default: null,
    },
    selected: {
      type: Boolean,
      default: false,
    },
  },
  inject: ['$registry'],
  computed: {
    containerAttrs() {
      const attrs = {}
      Object.keys(this.$attrs).forEach((key) => {
        if (!key.startsWith('on')) {
          attrs[key] = this.$attrs[key]
        }
      })
      return attrs
    },
    listenerAttrs() {
      const attrs = {}
      Object.keys(this.$attrs).forEach((key) => {
        if (key.startsWith('on')) {
          attrs[key] = this.$attrs[key]
        }
      })
      return attrs
    },
  },
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

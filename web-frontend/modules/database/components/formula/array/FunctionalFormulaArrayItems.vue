<!--
This component is used to render the formula array items, independently of the place.
It's used in the grid view cell, row edit modal, gallery card, etc.
-->
<template>
  <div :class="$attrs.class" :style="$attrs.style">
    <component
      :is="itemComponent"
      v-for="(item, index) in value || []"
      :key="index"
      v-bind="getAttrs(item, index)"
    />
    <slot />
  </div>
</template>

<script>
export default {
  name: 'FunctionalFormulaArrayItems',
  inheritAttrs: false,
  props: {
    field: { type: Object, required: true },
    value: { type: Array, default: () => [] },
  },
  computed: {
    formulaType() {
      return this.$registry.get('formula_type', this.field.array_formula_type)
    },
    itemComponent() {
      return this.formulaType.getFunctionalFieldArrayComponent()
    },
    componentAttrs() {
      // Forward everything except class/style to each item component because those
      // must be applied to the root element.
      const { class: _c, style: _s, ...rest } = this.$attrs
      return rest
    },
  },
  methods: {
    getValue(item) {
      return this.formulaType.getItemIsInNestedValueObjectWhenInArray()
        ? item && item.value
        : item
    },
    getAttrs(item, index) {
      return {
        ...this.componentAttrs,
        field: this.field,
        value: this.getValue(item),
        index,
      }
    },
  },
}
</script>

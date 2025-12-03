<template>
  <component
    :is="getComponent(field)"
    v-bind="$attrs"
    :read-only="true"
    class="active"
    v-on="$listeners"
  />
</template>

<script>
export default {
  name: 'GridViewFieldFormula',
  props: {
    field: { type: Object, required: true },
  },
  methods: {
    getComponent() {
      return this.$registry
        .get('formula_type', this.field.formula_type)
        .getGridViewFieldComponent(this.field)
    },
  },
}
</script>

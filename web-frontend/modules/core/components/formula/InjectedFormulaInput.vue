<template>
  <component
    :is="formulaComponent"
    :data-providers-allowed="dataProvidersAllowed || []"
    :enable-advanced-mode="enableAdvancedMode"
    v-bind="$attrs"
    @input="$emit('input', $event)"
  >
    <template #after-input>
      <slot name="after-input"></slot>
    </template>
  </component>
</template>

<script>
export default {
  name: 'InjectedFormulaInput',
  inject: ['formulaComponent', 'dataProvidersAllowed'],
  props: {
    enableAdvancedMode: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
}
</script>

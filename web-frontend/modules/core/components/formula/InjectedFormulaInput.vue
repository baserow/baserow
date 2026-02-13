<template>
  <component
    :is="formulaComponent"
    :data-providers-allowed="dataProvidersAllowed || []"
    v-bind="$attrs"
    @input="$emit('update:modelValue', $event)"
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
  emits: ['update:modelValue'],
}
</script>

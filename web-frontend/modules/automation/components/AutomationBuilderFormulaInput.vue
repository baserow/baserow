<template>
  <FormulaInputField
    v-bind="$attrs"
    required
    :value="formulaStr"
    :data-providers="dataProviders"
    :application-context="applicationContext"
    @input="updatedFormulaStr"
  />
</template>

<script setup>
import { inject, computed, useContext } from '@nuxtjs/composition-api'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'

const props = defineProps({
  value: { type: Object, required: false, default: () => ({}) },
  dataProvidersAllowed: { type: Array, required: false, default: () => [] },
})

const applicationContext = inject('applicationContext')

const { app } = useContext()
const dataProviders = computed(() => {
  return props.dataProvidersAllowed.map((dataProviderName) =>
    app.$registry.get('automationDataProvider', dataProviderName)
  )
})

/**
 * Extract the formula string from the value object, the FormulaInputField
 * component only needs the formula string itself.
 * @returns {String} The formula string.
 */
const formulaStr = computed(() => {
  return props.value.formula
})

/**
 * When `FormulaInputField` emits a new formula string, we need to emit the
 * entire value object with the updated formula string.
 * @param {String} newFormulaStr The new formula string.
 */
const emit = defineEmits(['input'])
const updatedFormulaStr = (newFormulaStr) => {
  emit('input', { ...props.value, formula: newFormulaStr })
}
</script>

<template>
  <FormulaInputField
    v-bind="$attrs"
    required
    :value="formulaStr"
    :data-providers="dataProviders"
    :application-context="applicationContext"
    enable-advanced-mode
    :mode="currentMode"
    @input="updatedFormulaStr"
    @mode-changed="updateMode"
  />
</template>

<script setup>
import { ref, watch } from 'vue'
import { inject, computed, useContext } from '@nuxtjs/composition-api'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'

const props = defineProps({
  value: { type: [Object, String], required: false, default: () => ({}) },
  dataProvidersAllowed: { type: Array, required: false, default: () => [] },
})

const applicationContext = inject('applicationContext')
const currentMode = ref(props.value.mode)

watch(
  () => props.value.mode,
  (newMode) => {
    if (newMode) {
      currentMode.value = newMode
    }
  }
)

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
  emit('input', {
    ...props.value,
    formula: newFormulaStr,
    mode: currentMode.value,
  })
}

const updateMode = (newMode) => {
  currentMode.value = newMode
}
</script>

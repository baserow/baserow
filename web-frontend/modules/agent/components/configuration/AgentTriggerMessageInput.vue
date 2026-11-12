<template>
  <FormulaInputField
    :value="modelValue?.formula || ''"
    :nodes-hierarchy="nodesHierarchy"
    :mode="mode"
    :disabled="disabled"
    :placeholder="placeholder"
    context-position="left"
    :validation-context="{ dataProviderRegistry: dataProviders }"
    @input="emitFormula"
    @update:mode="mode = $event"
  />
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import { buildFormulaFunctionNodes } from '@baserow/modules/core/formula'
import { getDataNodesFromDataProvider } from '@baserow/modules/core/utils/dataProviders'

const props = defineProps({
  /** The message formula object: `formula`, `mode` and `version`. */
  modelValue: { type: Object, default: null },
  placeholder: { type: String, default: null },
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const app = useNuxtApp()
const applicationContext = inject('applicationContext')
// A mode switch alone is not saved: it takes effect with the next formula edit.
const mode = ref(props.modelValue?.mode || 'simple')
watch(
  () => props.modelValue?.mode,
  (newMode) => {
    if (newMode) mode.value = newMode
  }
)
const dataProviders = computed(() => [
  app.$registry.get('agentDataProvider', 'trigger'),
])
const nodesHierarchy = computed(() => {
  const dataNodes = getDataNodesFromDataProvider(
    dataProviders.value,
    applicationContext
  )
  return [
    {
      name: app.$i18n.t('runtimeFormulaTypes.formulaTypeData'),
      type: 'data',
      icon: 'iconoir-database',
      nodes: dataNodes,
      empty: dataNodes.length === 0,
      emptyText: app.$i18n.t('runtimeFormulaTypes.formulaTypeDataEmpty'),
    },
    ...buildFormulaFunctionNodes(app),
  ]
})

/**
 * Emits the formula object with the edited formula and the current mode.
 *
 * @param {string} formula The edited formula.
 */
function emitFormula(formula) {
  emit('update:modelValue', { ...props.modelValue, formula, mode: mode.value })
}
</script>

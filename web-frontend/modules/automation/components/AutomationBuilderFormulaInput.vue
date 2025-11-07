<template>
  <FormulaInputField
    v-bind="$attrs"
    required
    :value="formulaStr"
    :nodes-hierarchy="nodesHierarchy"
    context-position="left"
    :mode="localMode"
    @update:mode="updateMode"
    @input="updatedFormulaStr"
  />
</template>

<script setup>
import {
  inject,
  computed,
  useContext,
  ref,
  watch,
} from '@nuxtjs/composition-api'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import { buildFormulaFunctionNodes } from '@baserow/modules/core/formula'
import { getDataNodesFromDataProvider } from '@baserow/modules/core/utils/dataProviders'

const props = defineProps({
  value: { type: [Object, String], required: false, default: () => ({}) },
  dataProvidersAllowed: { type: Array, required: false, default: () => [] },
})

const applicationContext = inject('applicationContext')

const emit = defineEmits(['input'])

// Local mode state
const localMode = ref(props.value.mode || 'simple')

// Watch for external changes to the mode
watch(
  () => props.value.mode,
  (newMode) => {
    if (newMode !== undefined && newMode !== localMode.value) {
      localMode.value = newMode
    }
  }
)

const { app } = useContext()

const dataProviders = computed(() => {
  return props.dataProvidersAllowed.map((dataProviderName) =>
    app.$registry.get('automationDataProvider', dataProviderName)
  )
})

const nodesHierarchy = computed(() => {
  const hierarchy = []

  const filteredDataNodes = getDataNodesFromDataProvider(
    dataProviders.value,
    applicationContext
  )

  hierarchy.push({
    name: app.i18n.t('runtimeFormulaTypes.formulaTypeData'),
    type: 'data',
    icon: 'iconoir-database',
    nodes: filteredDataNodes,
    empty: filteredDataNodes.length === 0,
    emptyText: app.i18n.t('runtimeFormulaTypes.formulaTypeDataEmpty'),
  })

  // Add functions and operators from the registry
  const formulaNodes = buildFormulaFunctionNodes(app)
  hierarchy.push(...formulaNodes)

  return hierarchy
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
const updatedFormulaStr = (newFormulaStr) => {
  emit('input', {
    ...props.value,
    formula: newFormulaStr,
    mode: localMode.value,
  })
}

/**
 * When the mode changes, update the local mode value only
 * @param {String} newMode The new mode value
 */
const updateMode = (newMode) => {
  localMode.value = newMode
}
</script>

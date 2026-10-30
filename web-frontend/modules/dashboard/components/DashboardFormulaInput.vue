<template>
  <FormulaInputField
    v-bind="$attrs"
    required
    :value="modelValue.formula"
    :mode="localMode"
    :nodes-hierarchy="nodesHierarchy"
    :validation-context="{
      dataProviderRegistry: dataProviders,
      applicationContext,
      parseDataProviderPath: parseDashboardFormulaPath,
    }"
    context-position="left"
    @update:mode="localMode = $event"
    @input="updatedFormulaStr"
  >
    <template v-if="$slots['raw-input']" #raw-input="slotProps">
      <slot name="raw-input" v-bind="slotProps"></slot>
    </template>
  </FormulaInputField>
</template>

<script setup>
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import { getDataNodesFromDataProvider } from '@baserow/modules/core/utils/dataProviders'
import { buildFormulaFunctionNodes } from '@baserow/modules/core/formula'
import { parseDashboardFormulaPath } from '@baserow/modules/dashboard/utils/filter'

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  dataProvidersAllowed: { type: Array, default: () => [] },
})

const emit = defineEmits(['input'])
const app = useNuxtApp()
const applicationContext = inject(
  'dashboardApplicationContext',
  computed(() => ({}))
)
const dataProviders = computed(() =>
  props.dataProvidersAllowed.map((name) =>
    app.$registry.get('dashboardDataProvider', name)
  )
)
const nodesHierarchy = computed(() => {
  const nodes = getDataNodesFromDataProvider(
    dataProviders.value,
    unref(applicationContext)
  )
  return [
    ...(nodes.length
      ? [
          {
            name: app.$i18n.t('runtimeFormulaTypes.formulaTypeData'),
            type: 'data',
            icon: 'iconoir-database',
            nodes,
          },
        ]
      : []),
    ...buildFormulaFunctionNodes(app),
  ]
})
const localMode = ref(props.modelValue.mode || 'simple')

watch(
  () => props.modelValue.mode,
  (mode) => {
    if (mode !== undefined) {
      localMode.value = mode
    }
  }
)

const updatedFormulaStr = (formula) => {
  emit('input', { ...props.modelValue, formula, mode: localMode.value })
}
</script>

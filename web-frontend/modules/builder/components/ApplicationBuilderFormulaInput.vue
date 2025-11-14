<template>
  <FormulaInputField
    v-bind="$attrs"
    required
    :value="formulaStr"
    :mode="localMode"
    :loading="dataExplorerLoading"
    :nodes-hierarchy="nodesHierarchy"
    :context-position="isInSidePanel ? 'left' : 'bottom'"
    @input="updatedFormulaStr"
    @update:mode="updateMode"
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
import { DataSourceDataProviderType } from '@baserow/modules/builder/dataProviderTypes'
import { buildFormulaFunctionNodes } from '@baserow/modules/core/formula'
import { getDataNodesFromDataProvider } from '@baserow/modules/core/utils/dataProviders'
import { useApplicationContext } from '@baserow/modules/builder/mixins/useApplicationContext'

const props = defineProps({
  value: {
    type: Object,
    required: false,
    default: () => ({}),
  },
  dataProvidersAllowed: {
    type: Array,
    required: false,
    default: () => [],
  },
  applicationContextAdditions: {
    type: Object,
    required: false,
    default: undefined,
  },
})

const applicationContext = useApplicationContext(
  props.applicationContextAdditions
)

const elementPage = inject('elementPage')

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

const { app, store } = useContext()

const isInSidePanel = computed(() => {
  return applicationContext.value?.element !== undefined
})

const dataProviders = computed(() => {
  return props.dataProvidersAllowed.map((dataProviderName) =>
    app.$registry.get('builderDataProvider', dataProviderName)
  )
})

const nodesHierarchy = computed(() => {
  const hierarchy = []

  const filteredDataNodes = getDataNodesFromDataProvider(
    dataProviders.value,
    applicationContext.value
  )

  if (filteredDataNodes.length > 0) {
    hierarchy.push({
      name: app.i18n.t('runtimeFormulaTypes.formulaTypeData'),
      type: 'data',
      icon: 'iconoir-database',
      nodes: filteredDataNodes,
    })
  }

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

const dataSourceLoading = computed(() => {
  return store.getters['dataSource/getLoading'](elementPage)
})

const dataSourceContentLoading = computed(() => {
  return store.getters['dataSourceContent/getLoading'](elementPage)
})

/**
 * This mapping defines which data providers are affected by what loading states.
 * Since not all data providers are always used in every data explorer we
 * shouldn't put the data explorer in a loading state whenever some inaccessible
 * data is loading.
 */
const dataProviderLoadingMap = computed(() => {
  return {
    [DataSourceDataProviderType.getType()]:
      dataSourceLoading.value || dataSourceContentLoading.value,
  }
})

const dataExplorerLoading = computed(() => {
  return props.dataProvidersAllowed.some(
    (dataProviderName) => dataProviderLoadingMap.value[dataProviderName]
  )
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

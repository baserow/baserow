<template>
  <FormulaInputField
    v-bind="$attrs"
    required
    :value="formulaStr"
    :mode="localMode"
    :format="localFormat"
    :loading="dataExplorerLoading"
    :nodes-hierarchy="nodesHierarchy"
    :context-position="isInSidePanel ? 'left' : 'bottom'"
    :validation-context="{ dataProviderRegistry: dataProviders }"
    @input="updatedFormulaStr"
    @update:mode="updateMode"
    @update:format="updateFormat"
  >
    <template v-if="$slots['raw-input']" #raw-input="slotProps">
      <slot name="raw-input" v-bind="slotProps"></slot>
    </template>
  </FormulaInputField>
</template>

<script setup>
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import { DataSourceDataProviderType } from '@baserow/modules/builder/dataProviderTypes'
import { buildFormulaFunctionNodes } from '@baserow/modules/core/formula'
import { getDataNodesFromDataProvider } from '@baserow/modules/core/utils/dataProviders'
import { useApplicationContext } from '@baserow/modules/builder/mixins/useApplicationContext'
import { BASEROW_FORMULA_FORMAT_PLAIN } from '@baserow/modules/core/formula/constants'

const props = defineProps({
  value: {
    type: Object,
    required: false,
    default: undefined,
  },
  modelValue: {
    type: Object,
    required: false,
    default: undefined,
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

const emit = defineEmits(['input', 'update:modelValue'])

const currentValue = computed(() => {
  return props.modelValue !== undefined ? props.modelValue : props.value || {}
})

// Local mode state
const localMode = ref(currentValue.value.mode || 'simple')

// Watch for external changes to the mode
watch(
  () => currentValue.value.mode,
  (newMode) => {
    if (newMode !== undefined && newMode !== localMode.value) {
      localMode.value = newMode
    }
  }
)

// Local format state. A value without a `format` key is plain.
const localFormat = ref(
  currentValue.value.format || BASEROW_FORMULA_FORMAT_PLAIN
)

// Watch for external changes to the format. Unlike the mode, a key that goes
// missing is a change too: it means the value went back to plain.
watch(
  () => currentValue.value.format,
  (newFormat) => {
    const format = newFormat || BASEROW_FORMULA_FORMAT_PLAIN
    if (format !== localFormat.value) {
      localFormat.value = format
    }
  }
)

const app = useNuxtApp()
const { $store } = app

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
      name: app.$i18n.t('runtimeFormulaTypes.formulaTypeData'),
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
 * Extract the expression string from the value object, the FormulaInputField
 * component only needs the expression string itself.
 * @returns {String} The expression string.
 */
const formulaStr = computed(() => {
  // Legacy stored values can contain `formula: null`; `FormulaInputField`
  // expects a string.
  return currentValue.value.formula || ''
})

const dataSourceLoading = computed(() => {
  return $store.getters['dataSource/getLoading'](elementPage)
})

const dataSourceContentLoading = computed(() => {
  return $store.getters['dataSourceContent/getLoading'](elementPage)
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
 * Builds the value object to emit from an expression string, the local mode
 * and the local format. The `format` key is only set when it isn't plain: a
 * missing key means plain, which keeps plain values identical to the ones
 * stored before formats existed.
 * @param {String} formula The expression string.
 * @returns {Object} The value object.
 */
const buildValue = (formula) => {
  const value = {
    ...currentValue.value,
    formula,
    mode: localMode.value,
  }
  if (localFormat.value !== BASEROW_FORMULA_FORMAT_PLAIN) {
    value.format = localFormat.value
  } else {
    delete value.format
  }
  return value
}

const emitValue = (value) => {
  emit('input', value)
  emit('update:modelValue', value)
}

/**
 * When `FormulaInputField` emits a new expression string, we need to emit the
 * entire value object with the updated expression string.
 * @param {String} newFormulaStr The new expression string.
 */
const updatedFormulaStr = (newFormulaStr) => {
  emitValue(buildValue(newFormulaStr))
}

/**
 * When the mode changes, update the local mode value only
 * @param {String} newMode The new mode value
 */
const updateMode = (newMode) => {
  localMode.value = newMode
}

/**
 * When the format changes, emit right away. Unlike the mode, which only takes
 * effect once the text changes, picking a format is a change by itself and
 * must persist without an edit to the formula.
 * @param {String} newFormat The new format value
 */
const updateFormat = (newFormat) => {
  localFormat.value = newFormat
  emitValue(buildValue(formulaStr.value ?? ''))
}
</script>

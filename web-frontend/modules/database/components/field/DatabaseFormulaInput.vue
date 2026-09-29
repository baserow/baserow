<template>
  <FormulaInputField
    v-bind="$attrs"
    :value="formulaStr"
    :mode="localMode"
    :nodes-hierarchy="nodesHierarchy"
    :validation-context="{ dataProviderRegistry: dataProviders }"
    @input="onFormulaChanged"
    @update:mode="updateMode"
  />
</template>

<script>
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import { buildFormulaFunctionNodes } from '@baserow/modules/core/formula'
import { getDataNodesFromDataProvider } from '@baserow/modules/core/utils/dataProviders'

/**
 * The database counterpart to `ApplicationBuilderFormulaInput`, provided as
 * `formulaComponent` so `InjectedFormulaInput` has something to render.
 * Without a host providing it, the injection is undefined and nothing renders.
 */
export default {
  name: 'DatabaseFormulaInput',
  components: { FormulaInputField },
  inject: {
    // What the data providers read to build the explorer tree. Without it the
    // explorer simply shows no data nodes.
    databaseFormulaContext: { from: 'databaseFormulaContext', default: null },
  },
  inheritAttrs: false,
  props: {
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
  },
  emits: ['input', 'update:modelValue'],
  data() {
    const current = this.modelValue !== undefined ? this.modelValue : this.value
    return { localMode: current?.mode || 'simple' }
  },
  computed: {
    currentValue() {
      return (
        (this.modelValue !== undefined ? this.modelValue : this.value) || {}
      )
    },
    formulaStr() {
      // Legacy stored values can contain `formula: null`; `FormulaInputField`
      // expects a string.
      return this.currentValue.formula || ''
    },
    applicationContext() {
      return this.databaseFormulaContext || {}
    },
    dataProviders() {
      return this.dataProvidersAllowed.map((name) =>
        this.$registry.get('databaseDataProvider', name)
      )
    },
    /**
     * Built from the registry rather than from anything the user is editing,
     * so this resolves once per input instead of on every keystroke.
     */
    functionNodes() {
      return buildFormulaFunctionNodes(this)
    },
    nodesHierarchy() {
      const hierarchy = []
      const dataNodes = getDataNodesFromDataProvider(
        this.dataProviders,
        this.applicationContext
      )
      if (dataNodes.length > 0) {
        hierarchy.push({
          name: this.$t('runtimeFormulaTypes.formulaTypeData'),
          type: 'data',
          icon: 'iconoir-database',
          nodes: dataNodes,
        })
      }
      hierarchy.push(...this.functionNodes)
      return hierarchy
    },
  },
  watch: {
    'currentValue.mode'(newMode) {
      if (newMode !== undefined && newMode !== this.localMode) {
        this.localMode = newMode
      }
    },
  },
  methods: {
    /**
     * The field emits the expression only; put it back on the value object.
     */
    onFormulaChanged(newFormulaStr) {
      const newValue = {
        ...this.currentValue,
        formula: newFormulaStr,
        mode: this.localMode,
      }
      this.$emit('input', newValue)
      this.$emit('update:modelValue', newValue)
    },
    updateMode(newMode) {
      this.localMode = newMode
    },
  },
}
</script>

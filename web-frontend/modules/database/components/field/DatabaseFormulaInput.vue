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
 * The database module's counterpart to `ApplicationBuilderFormulaInput`: the
 * component a database field form provides as `formulaComponent`, so the
 * shared `InjectedFormulaInput` has something to render.
 *
 * `InjectedFormulaInput` renders `<component :is="formulaComponent">` and
 * injects nothing else, so without a host providing this the injection is
 * undefined and Vue renders a bare comment node where the input should be.
 */
export default {
  name: 'DatabaseFormulaInput',
  components: { FormulaInputField },
  inject: {
    // The context the data providers read to build the explorer tree, e.g.
    // `{ fields }` for the row the button was clicked on. Optional: without it
    // the explorer just shows no data nodes.
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
      return this.currentValue.formula
    },
    applicationContext() {
      return this.databaseFormulaContext || {}
    },
    dataProviders() {
      return this.dataProvidersAllowed.map((name) =>
        this.$registry.get('databaseDataProvider', name)
      )
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
      hierarchy.push(...buildFormulaFunctionNodes(this))
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
     * `FormulaInputField` emits the expression string only, so put it back on
     * the value object the caller v-models.
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

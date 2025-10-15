<template>
  <FormulaInputField
    v-bind="$attrs"
    required
    :value="formulaStr"
    :data-explorer-loading="dataExplorerLoading"
    :data-providers="dataProviders"
    :application-context="applicationContext"
    @input="updatedFormulaStr"
  />
</template>

<script>
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import { DataSourceDataProviderType } from '@baserow/modules/builder/dataProviderTypes'
import applicationContext from '@baserow/modules/builder/mixins/applicationContext'

export default {
  name: 'ApplicationBuilderFormulaInput',
  components: { FormulaInputField },
  mixins: [applicationContext],
  inject: {
    elementPage: {
      from: 'elementPage',
    },
    builder: {
      from: 'builder',
    },
    mode: {
      from: 'mode',
    },
  },
  props: {
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
  },
  computed: {
    /**
     * Extract the formula string from the value object, the FormulaInputField
     * component only needs the formula string itself.
     * @returns {String} The formula string.
     */
    formulaStr() {
      return this.value.formula
    },
    dataSourceLoading() {
      return this.$store.getters['dataSource/getLoading'](this.elementPage)
    },
    dataSourceContentLoading() {
      return this.$store.getters['dataSourceContent/getLoading'](
        this.elementPage
      )
    },
    dataProviders() {
      return this.dataProvidersAllowed.map((dataProviderName) =>
        this.$registry.get('builderDataProvider', dataProviderName)
      )
    },
    /**
     * This mapping defines which data providers are affected by what loading states.
     * Since not all data providers are always used in every data explorer we
     * shouldn't put the data explorer in a loading state whenever some inaccessible
     * data is loading.
     */
    dataProviderLoadingMap() {
      return {
        [DataSourceDataProviderType.getType()]:
          this.dataSourceLoading || this.dataSourceContentLoading,
      }
    },
    dataExplorerLoading() {
      return this.dataProvidersAllowed.some(
        (dataProviderName) => this.dataProviderLoadingMap[dataProviderName]
      )
    },
  },
  methods: {
    /**
     * When `FormulaInputField` emits a new formula string, we need to emit the
     * entire value object with the updated formula string.
     * @param {String} newFormulaStr The new formula string.
     */
    updatedFormulaStr(newFormulaStr) {
      this.$emit('input', { ...this.value, formula: newFormulaStr })
    },
  },
}
</script>

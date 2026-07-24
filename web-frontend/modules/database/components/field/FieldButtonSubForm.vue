<template>
  <div class="context__form-container">
    <FormGroup
      small-label
      :label="$t('fieldButtonSubForm.label')"
      :error="fieldHasErrors('label')"
    >
      <FormInput
        v-model="v$.values.label.$model"
        :placeholder="$t('fieldButtonSubForm.labelPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      required
      :label="$t('fieldButtonSubForm.url')"
      :error="v$.values.url_formula?.formula.$error || urlInvalid"
    >
      <FormulaInputField
        :value="formulaStr"
        :mode="localMode"
        :nodes-hierarchy="nodesHierarchy"
        :placeholder="$t('fieldButtonSubForm.urlPlaceholder')"
        :validation-context="{ dataProviderRegistry: dataProviders }"
        @input="updatedFormulaStr"
        @update:mode="updateMode"
        @update:invalid="urlInvalid = $event"
      />
      <template #error>
        {{
          urlInvalid
            ? $t('fieldButtonSubForm.invalidUrl')
            : $t('error.requiredField')
        }}
      </template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import { buildFormulaFunctionNodes } from '@baserow/modules/core/formula'
import { getDataNodesFromDataProvider } from '@baserow/modules/core/utils/dataProviders'

export default {
  name: 'FieldButtonSubForm',
  components: { FormulaInputField },
  mixins: [form, fieldSubForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['label', 'url_formula'],
      values: {
        label: '',
        url_formula: { formula: '', mode: 'simple' },
      },
      localMode: 'simple',
      urlInvalid: false,
    }
  },
  computed: {
    formulaStr() {
      return this.values.url_formula.formula
    },
    applicationContext() {
      const context = {}
      Object.defineProperty(context, 'fields', {
        enumerable: true,
        get: () =>
          this.allFieldsInTable.filter((f) => f.id !== this.defaultValues.id),
      })
      return context
    },
    dataProviders() {
      return [this.$registry.get('databaseDataProvider', 'fields')]
    },
    nodesHierarchy() {
      const hierarchy = []
      const filteredDataNodes = getDataNodesFromDataProvider(
        this.dataProviders,
        this.applicationContext
      )
      if (filteredDataNodes.length > 0) {
        hierarchy.push({
          name: this.$t('runtimeFormulaTypes.formulaTypeData'),
          type: 'data',
          icon: 'iconoir-database',
          nodes: filteredDataNodes,
        })
      }
      hierarchy.push(...buildFormulaFunctionNodes(this))
      return hierarchy
    },
  },
  watch: {
    'values.url_formula.mode': {
      handler(newMode) {
        if (newMode && newMode !== this.localMode) {
          this.localMode = newMode
        }
      },
      immediate: true,
    },
  },
  methods: {
    /**
     * The formula input only emits parseable formulas, so block submission
     * while the editor content is invalid instead of saving a stale formula.
     */
    isFormValid(deep = false) {
      return !this.urlInvalid && form.methods.isFormValid.call(this, deep)
    },
    updatedFormulaStr(newFormulaStr) {
      this.v$.values.url_formula.formula.$model = newFormulaStr
    },
    updateMode(newMode) {
      this.localMode = newMode
      this.values.url_formula = { ...this.values.url_formula, mode: newMode }
    },
  },
  validations() {
    return {
      values: {
        label: {},
        url_formula: { formula: { required } },
      },
    }
  },
}
</script>

<template>
  <div class="context__form-container">
    <FieldSelectThroughFieldSubForm
      :fields="allFieldsInTable"
      :database="database"
      :default-values="defaultValues"
      @input="selectedThroughField = $event"
    ></FieldSelectThroughFieldSubForm>
    <FieldSelectTargetFieldSubForm
      :database="database"
      :table="table"
      :through-field="selectedThroughField"
      :default-values="defaultValues"
      :label="$t('fieldLookupSubForm.selectTargetFieldLabel')"
      @input="selectedTargetField = $event"
    ></FieldSelectTargetFieldSubForm>
    <template v-if="selectedTargetField">
      <FormulaTypeSubForms
        :default-values="subFormDefaultValues"
        :formula-type="targetFieldFormulaType"
        :table="table"
        :view="view"
        :all-fields-in-table="allFieldsInTable"
        :database="database"
      >
      </FormulaTypeSubForms>
    </template>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FormulaTypeSubForms from '@baserow/modules/database/components/formula/FormulaTypeSubForms'
import FieldSelectThroughFieldSubForm from '@baserow/modules/database/components/field/FieldSelectThroughFieldSubForm'
import FieldSelectTargetFieldSubForm from '@baserow/modules/database/components/field/FieldSelectTargetFieldSubForm'

export default {
  name: 'FieldLookupSubForm',
  components: {
    FieldSelectThroughFieldSubForm,
    FieldSelectTargetFieldSubForm,
    FormulaTypeSubForms,
  },
  mixins: [form, fieldSubForm],
  data() {
    return {
      selectedThroughField: null,
      selectedTargetField: null,
      allowedValues: [],
      values: {},
      errorFromServer: null,
      subFormDefaultValues: {},
    }
  },
  computed: {
    targetFieldFormulaType() {
      if (this.selectedTargetField) {
        return this.getFormulaType(this.selectedTargetField)
      }
      return 'unknown'
    },
  },
  watch: {
    defaultValues: {
      handler(newDefaultValues) {
        this.subFormDefaultValues = { ...newDefaultValues }
      },
      immediate: true,
    },
    selectedTargetField: {
      handler(newTargetField) {
        if (!newTargetField) {
          return
        }
        const fieldType = this.$registry.get('field', newTargetField.type)
        const formulaType = fieldType.toBaserowFormulaType(newTargetField)

        const formulaTypeChanged =
          formulaType && this.getFormulaType(this.defaultValues) !== formulaType

        // New field or different type, use the relevant settings from the target field
        const fieldValues = this.defaultValues
        if (!fieldValues.id || formulaTypeChanged) {
          for (const key in this.selectedTargetField) {
            if (key.startsWith(formulaType)) {
              this.subFormDefaultValues[key] = this.selectedTargetField[key]
            }
          }
        }
      },
    },
  },
  validations: {},
  methods: {
    getFormulaType(field) {
      return field.array_formula_type || field.formula_type || field.type
    },
    handleErrorByForm(error) {
      if (
        [
          'ERROR_WITH_FORMULA',
          'ERROR_FIELD_SELF_REFERENCE',
          'ERROR_FIELD_CIRCULAR_REFERENCE',
        ].includes(error.handler.code)
      ) {
        this.errorFromServer = error.handler.detail
        return true
      } else {
        return false
      }
    },
    reset() {
      form.methods.reset.call(this)
      this.errorFromServer = null
    },
  },
}
</script>

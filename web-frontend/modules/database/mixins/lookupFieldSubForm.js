import form from '@baserow/modules/core/mixins/form'

export default {
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
      /**
       * Updates sub form defaults based on the selected target field.
       * For new fields with untouched forms, always suggest target field settings.
       * For existing fields, suggest settings only if the formula type changes.
       */
      handler(newTargetField, oldTargetField) {
        if (!newTargetField) {
          return
        }
        const fieldId = this.defaultValues.id
        const newField = !fieldId
        const cleanForm = !this.$refs.subForm?.isDirty()

        const newFieldCleanFormAndNewTarget =
          newField && cleanForm && newTargetField?.id !== oldTargetField?.id

        const existingFieldButDifferentType =
          !newField && !this.matchTargetFieldType(newTargetField)

        const shouldSuggestDefaults =
          newFieldCleanFormAndNewTarget || existingFieldButDifferentType

        const fieldType = this.$registry.get('field', newTargetField.type)
        const formulaType = fieldType.toBaserowFormulaType(newTargetField)

        // New field or different type, use the relevant settings from the target field
        if (shouldSuggestDefaults) {
          const defaults = {}
          for (const key in this.selectedTargetField) {
            if (key.startsWith(formulaType)) {
              defaults[key] = this.selectedTargetField[key]
            }
          }
          this.subFormDefaultValues = {
            ...this.subFormDefaultValues,
            ...defaults,
          }
          this.$nextTick(() => this.$refs.subForm.reset())
        }
      },
    },
  },
  methods: {
    /**
     * Verify if the final formula type match the target field type.
     */
    matchTargetFieldType(targetField) {
      const field = this.defaultValues
      return (
        field?.type === this.fieldType &&
        (field?.formula_type === targetField?.type ||
          field?.array_formula_type === targetField?.type)
      )
    },
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

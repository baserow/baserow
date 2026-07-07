export default {
  props: {
    table: {
      type: Object,
      required: true,
    },
    fieldType: {
      type: String,
      required: false,
      default: '',
    },
    view: {
      type: Object,
      required: true,
    },
    primary: {
      type: Boolean,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    fieldConstraints: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  computed: {
    hasViewLevelDefaultValue() {
      const fieldId = this.defaultValues?.id
      if (!fieldId || !this.view?.default_row_values) {
        return false
      }
      return this.view.default_row_values.some(
        (item) => item.field === fieldId && item.enabled
      )
    },
    isDefaultValueFieldDisabled() {
      if (!this.fieldConstraints || this.fieldConstraints.length === 0) {
        return false
      }

      return this.fieldConstraints.some(
        (constraint) =>
          constraint.type_name &&
          !this.$registry
            .getSpecificConstraint(
              'fieldConstraint',
              constraint.type_name,
              this.fieldType
            )
            .canSupportDefaultValue()
      )
    },
  },
}

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
    formValues: {
      type: Object,
      required: true,
    },
  },
  methods: {
    isDefaultValueFieldDisabled(defaultValue, formValues) {
      if (
        !formValues.field_constraints ||
        formValues.field_constraints.length === 0
      ) {
        return false
      }

      return formValues.field_constraints.some(
        (constraint) =>
          constraint.type_name &&
          !this.$registry
            .getSpecificConstraint(
              'fieldConstraint',
              constraint.type_name,
              this.fieldType
            )
            ?.canSupportDefaultValue()
      )
    },
  },
}

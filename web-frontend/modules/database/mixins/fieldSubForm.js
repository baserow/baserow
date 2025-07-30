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

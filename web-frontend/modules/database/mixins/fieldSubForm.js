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
  },
  methods: {
    updateParentDefaultValue(newValue) {
      if (this.$parent && this.$parent.fieldDefaultValue !== undefined) {
        this.$parent.fieldDefaultValue = newValue
      }
    },
  },
}

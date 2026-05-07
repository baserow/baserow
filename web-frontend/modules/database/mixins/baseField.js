/**
 * A mixin that can be used by a row edit modal component. It introduces the props that
 * will be passed by the RowEditModalField component.
 */
export default {
  props: {
    /**
     * The workspace ID of the workspace where parent table and database are in.
     */
    workspaceId: {
      type: Number,
      required: true,
      default: null,
    },
    /**
     * Contains the field type object. Because each field type can have different
     * settings you need this in order to render the correct component or implement
     * correct validation.
     */
    field: {
      type: Object,
      required: true,
    },
    /**
     * The value of the grid field, this could for example for a number field 10,
     * text field 'Random string' etc.
     */
    value: {
      type: [String, Number, Object, Boolean, Array],
      required: false,
    },
    /**
     * The row object that is being edited. This can be used to reference other
     * fields in the same row.
     */
    row: {
      type: Object,
      required: false,
      default: null,
    },
    /**
     * The table fields of the parent table. This can be used to reference other
     * fields in the same table.
     */
    allFieldsInTable: {
      type: Array,
      required: false,
      default: null,
    },
  },
  computed: {
    valid() {
      return this.isValid()
    },
    error() {
      return this.getError()
    },
  },
  methods: {
    isValid() {
      return this.getError() === null
    },
    getError() {
      return this.getValidationError(this.value)
    },
    /**
     * Should return a validation error message in string format if there is
     * any.
     */
    getValidationError(value) {
      const fieldType = this.$registry.get('field', this.field.type)
      const error = fieldType.getValidationError(this.field, value)
      return error
    },
  },
}

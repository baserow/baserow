import baseField from '@baserow/modules/database/mixins/baseField'

/**
 * A mixin that can be used by a row edit modal component. It introduces the props that
 * will be passed by the RowEditModalField component.
 */
export default {
  mixins: [baseField],
  props: {
    readOnly: {
      type: Boolean,
      required: true,
    },
    /**
     * Indicates if the value is required. If so, then an error is added when the
     * value is not provided.
     */
    required: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Indicates if the input has been touched by the user. If not touched then the
     * error messages are not displayed because that might be confusing for the
     * user. By default this is set to true because that's expected in the row
     * modal. When using it as a form that is first rendered in an empty state, then
     * this value should be false.
     */
    touched: {
      type: Boolean,
      required: false,
      default: true,
    },
    rowIsCreated: {
      type: Boolean,
      required: false,
      default: () => true,
    },
  },
  methods: {
    /**
     * Extends the getValidationError and add the required error message if this
     * field value is required.
     */
    getValidationError(value) {
      const error = baseField.methods.getValidationError.call(this, value)

      if (this.required && error === null) {
        const fieldType = this.$registry.get('field', this.field.type)
        const empty = fieldType.isEmpty(this.field, value)
        if (empty) {
          return this.$t('error.requiredField')
        }
      }

      return error
    },
    touch() {
      if (!this.touched) {
        this.$emit('touched')
      }
    },
  },
}

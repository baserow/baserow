import { clone } from '@baserow/modules/core/utils/object'

/**
 * This mixin introduces some helper functions for form components where the
 * whole component existence is based on being a form.
 */
export default {
  props: {
    defaultValues: {
      type: Object,
      required: false,
      default: () => {
        return {}
      },
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      // A list of values that the form allows. If null all values are allowed.
      allowedValues: null,
      // Setting to false make it possible to temporarily
      // prevent emitting values when they change.
      // Use setEmitValues(value) method to include children
      // forms.
      emitValues: true,
      // Setting to true makes it possible to not
      // emit values the first time values are set in
      // the form.
      skipFirstValuesEmit: false,
    }
  },
  mounted() {
    for (const [key, value] of Object.entries(this.getDefaultValues())) {
      this.values[key] = value
    }
  },
  watch: {
    values: {
      handler(newValues) {
        if (this.skipFirstValuesEmit) {
          this.skipFirstValuesEmit = false
          return
        }
        if (this.emitValues) {
          this.emitChange(newValues)
        }
      },
      deep: true,
    },
  },
  methods: {
    /**
     * Returns whether a key of the given defaultValue should be handled by this
     * form component. This is useful when the defaultValues also contain other
     * values which must not be used when submitting. By default this implementation
     * is filtered by the list of `allowedValues`.
     */
    isAllowedKey(key) {
      if (this.allowedValues !== null) {
        return this.allowedValues.includes(key)
      }
      return true
    },
    /**
     * Returns all the provided default values filtered by the `isAllowedKey` method.
     */
    getDefaultValues() {
      return Object.keys(this.defaultValues).reduce((result, key) => {
        if (this.isAllowedKey(key)) {
          let value = this.defaultValues[key]

          // If the value is an array or object, it could be that it contains
          // references and we actually need a copy of the value here so that we don't
          // directly change existing variables when editing form values.
          if (
            Array.isArray(value) ||
            (typeof value === 'object' && value !== null)
          ) {
            value = clone(value)
          }

          result[key] = value
        }
        return result
      }, {})
    },
    /**
     * Combined with the FormElement component, this method make sure
     * to scroll to the first error field after a fail form submit.
     * It is particularly useful for small screen devices or for long
     * forms, helping the user to see the error message even if the
     * it is outside of the current viewport.
     */
    focusOnFirstError() {
      const firstError = this.$el.querySelector('[data-form-error]')
      if (firstError) {
        firstError.scrollIntoView({ behavior: 'smooth' })
      }
    },
    /**
     * Select all children that match the given predicate.
     * @param {Function} predicate a function that receive the current child as parameter and
     *   should return true if the child should be accepted.
     * @param {Boolean} deep true if you want to deeply search for child
     * @returns
     */
    getChildForms(predicate = (child) => 'isFormValid' in child, deep = false) {
      const children = []

      const getDeep = (child) => {
        if (predicate(child)) {
          children.push(child)
        }
        if (deep) {
          // Search into children of children
          child.$children.forEach(getDeep)
        }
      }

      for (const child of this.$children) {
        getDeep(child)
      }
      return children
    },
    touch(deep = false) {
      if ('v$' in this) {
        this.v$.$touch()
      }

      // Also touch all the child forms so that all the error messages are going to
      // be displayed.
      for (const child of this.getChildForms(
        (child) => 'touch' in child,
        deep
      )) {
        child.touch(deep)
      }
    },
    submit(deep = false) {
      if (this.selectedFieldIsDeactivated) {
        return
      }
      this.touch(deep)

      if (this.isFormValid(deep)) {
        this.$emit('submitted', this.getFormValues(deep))
      } else {
        this.$nextTick(() => this.focusOnFirstError())
      }
    },
    /**
     * Returns true if the field value has no errors
     */
    fieldHasErrors(fieldName) {
      // a field can be without any validators
      return this.v$.values[fieldName]?.$error || false
    },
    /**
     * Return the first validaten error message for the given field
     * @param {str} fieldName
     * @returns the error message or undefined if none.
     */
    getFirstErrorMessage(fieldName) {
      return this.v$.values[fieldName].$errors[0]?.$message
    },
    /**
     * Returns true is everything is valid.
     *
     * `deep` parameter allow to deeply search the form elements and not staying at the
     * first level of children.
     */
    isFormValid(deep = false) {
      // Some forms might not do any validation themselves. If they don't, then they
      // are by definition valid if their children are valid.

      const thisFormInvalid = 'v$' in this && this.v$.$invalid
      return !thisFormInvalid && this.areChildFormsValid(deep)
    },
    /**
     * Returns true if all the child form components are valid.
     */
    areChildFormsValid(deep = false) {
      return this.getChildForms((child) => 'isFormValid' in child, deep).every(
        (child) => child.isFormValid()
      )
    },
    /**
     * A method that can be overridden to do some mutations on the values before
     * calling the submitted event.
     */
    getFormValues(deep = false) {
      return Object.assign({}, this.values, this.getChildFormsValues(deep))
    },
    /**
     * Returns an object containing the values of the child forms.
     */
    getChildFormsValues(deep = false) {
      const children = this.getChildForms(
        (child) => 'getChildFormsValues' in child,
        deep
      )
      return Object.assign(
        {},
        ...children.map((child) => {
          return child.getFormValues(deep)
        })
      )
    },
    isDirty() {
      for (const [key, value] of Object.entries(this.getDefaultValues())) {
        if (this.values[key] !== value) return true
      }
      return false
    },
    /**
     * Resets the form and the child forms to its original state.
     *
     * `deep` parameter allow to deeply search the form elements and not staying at the
     * first level of children.
     */
    async reset(deep = false) {
      for (const [key, value] of Object.entries(this.getDefaultValues())) {
        this.values[key] = value
      }

      if ('v$' in this) {
        this.v$.$reset()
      }

      await this.$nextTick()

      // Also reset the child forms after a tick to allow default values to be updated.
      this.getChildForms((child) => 'reset' in child, deep).forEach((child) =>
        child.reset()
      )
    },
    /**
     * Sets emitValues property also to child forms.
     */
    setEmitValues(value) {
      this.emitValues = value
      this.getChildForms((child) => 'setEmitValues' in child, true).forEach(
        (child) => child.setEmitValues(value)
      )
    },
    /**
     * Returns if a child form has indicated it handled the error, false otherwise.
     */
    handleErrorByForm(error, deep = false) {
      let childHandledIt = false
      const children = this.getChildForms(
        (child) => 'handleErrorByForm' in child,
        deep
      )
      for (const child of children) {
        if (child.handleErrorByForm(error)) {
          childHandledIt = true
        }
      }
      return childHandledIt
    },
    emitChange(newValues) {
      this.$emit('values-changed', newValues)
    },
  },
}

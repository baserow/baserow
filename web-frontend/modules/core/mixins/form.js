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
    }
  },
  mounted() {
    this.values = Object.assign({}, this.values, this.getDefaultValues())
  },
  watch: {
    values: {
      deep: true,
      handler(newValues) {
        this.emitChange(newValues)
      },
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
    touch() {
      if ('$v' in this) {
        this.$v.$touch()
      }

      // Also touch all the child forms so that all the error messages are going to
      // be displayed.
      for (const child of this.$children) {
        if ('isFormValid' in child && '$v' in child) {
          child.touch()
        }
      }
    },
    submit() {
      if (this.selectedFieldIsDeactivated) {
        return
      }

      this.touch()

      if (this.isFormValid()) {
        this.$emit('submitted', this.getFormValues())
      } else {
        this.$nextTick(() => this.focusOnFirstError())
      }
    },
    /**
     * Returns true if the field value has no errors
     */
    fieldHasErrors(fieldName) {
      // a field can be without any validators
      return this.$v.values[fieldName]
        ? this.$v.values[fieldName].$error
        : false
    },
    getChildForms(deep = false) {
      const children = []
      const getDeep = (child) => {
        if ('isFormValid' in child) {
          children.push(child)
        } else if (deep) {
          child.$children.forEach(getDeep)
        }
      }

      for (const child of this.$children) {
        getDeep(child)
      }
      return children
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
      const thisFormInvalid = '$v' in this && this.$v.$invalid
      return !thisFormInvalid && this.areChildFormsValid(deep)
    },
    /**
     * Returns true if all the child form components are valid.
     */
    areChildFormsValid(deep = false) {
      for (const child of this.getChildForms(deep)) {
        if ('isFormValid' in child && !child.isFormValid()) {
          return false
        }
      }
      return true
    },
    /**
     * A method that can be overridden to do some mutations on the values before
     * calling the submitted event.
     */
    getFormValues() {
      return Object.assign({}, this.values, this.getChildFormsValues())
    },
    /**
     * Returns an object containing the values of the child forms.
     */
    getChildFormsValues() {
      return Object.assign(
        {},
        ...this.$children.map((child) => {
          return 'getChildFormsValues' in child ? child.getFormValues() : {}
        })
      )
    },
    /**
     * Resets the form and the child forms to its original state.
     *
     * `deep` parameter allow to deeply search the form elements and not staying at the
     * first level of children.
     */
    async reset(deep = false) {
      Object.assign(
        this.values,
        this.$options.data.call(this).values,
        this.getDefaultValues()
      )

      if ('$v' in this) {
        this.$v.$reset()
      }

      await this.$nextTick()

      // Also reset the child forms after a tick to allow default values to be updated.
      this.getChildForms(deep).forEach((child) => child.reset())
    },

    /**
     * Returns if a child form has indicated it handled the error, false otherwise.
     */
    handleErrorByForm(error) {
      let childHandledIt = false
      for (const child of this.$children) {
        if ('handleErrorByForm' in child && child.handleErrorByForm(error)) {
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

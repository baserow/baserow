import { mapActions } from 'vuex'
import element from '@baserow/modules/builder/mixins/element'
import { FormContainerElementType } from '@baserow/modules/builder/elementTypes'

export default {
  mixins: [element],
  data() {
    return {
      inputValue: null,
    }
  },
  mounted() {
    // When a form element is mounted, we want to set the initial value of the form
    // data in the store, but *only* after we have a fully complete `recordIndexPath`,
    // otherwise we will create two entries in the form data store: one for just the
    // elementId, and once the `recordIndexPath` is set, another one with the full path.
    const initialValue = this.elementType.getInitialFormDataValue(
      this.element,
      this.applicationContext
    )
    this.setFormData(initialValue)
  },
  computed: {
    uniqueElementId() {
      return this.elementType.uniqueElementId(
        this.element,
        this.applicationContext.recordIndexPath
      )
    },
    formElementData() {
      return this.$store.getters['formData/getElementFormEntry'](
        this.elementPage,
        this.uniqueElementId
      )
    },
    elementFormDataValue() {
      return this.formElementData?.value
    },
    formElementInvalid() {
      return this.$store.getters['formData/getElementInvalid'](
        this.elementPage,
        this.uniqueElementId
      )
    },
    displayFormDataError() {
      return (
        this.formElementTouched && this.formElementInvalid && !this.isEditMode
      )
    },
    errorMessage() {
      return this.displayFormDataError ? this.getErrorMessage() : ''
    },
    formElementTouched() {
      return this.$store.getters['formData/getElementTouched'](
        this.elementPage,
        this.uniqueElementId
      )
    },
    /**
     * Returns whether the form element is a descendant of a form container.
     * @returns {Boolean} If one or more ancestors is a form container.
     */
    isDescendantOfFormContainer() {
      return this.$store.getters['element/getAncestors'](
        this.elementPage,
        this.element
      ).some(({ type }) => type === FormContainerElementType.getType())
    },
  },
  methods: {
    ...mapActions({
      actionSetFormData: 'formData/setFormData',
    }),
    /*
     * When a form element has been modified (e.g. a user has inputted a value),
     * this method is responsible for updating the form data in the store, and
     * if it's not inside a form container, marking the form element as having
     * been 'touched' by the user.
     */
    handleFormElementChange(value) {
      this.setFormData(value)
      if (!this.isDescendantOfFormContainer) {
        this.onFormElementTouch()
      }
    },
    setFormData(value) {
      return this.actionSetFormData({
        page: this.elementPage,
        uniqueElementId: this.uniqueElementId,
        payload: {
          value,
          elementId: this.element.id,
          touched: this.formElementTouched,
          type: this.elementType.formDataType(this.element),
          isValid: this.elementType.isValid(
            this.element,
            value,
            this.applicationContext
          ),
        },
      })
    },
    /**
     * Responsible for marking this form element as being 'touched' by a
     * user. This will help influence whether to display validation errors.
     */
    onFormElementTouch() {
      this.$store.dispatch('formData/setElementTouched', {
        page: this.elementPage,
        wasTouched: true,
        uniqueElementId: this.uniqueElementId,
      })
    },
    /** Override this method to display the right error message */
    getErrorMessage() {
      return ''
    },
  },
  watch: {
    /**
     * When a form element's formData value changes.
     */
    elementFormDataValue: {
      handler(newValue) {
        this.inputValue = newValue
      },
      immediate: true,
    },
    inputValue(newValue) {
      this.handleFormElementChange(newValue)
    },
  },
}

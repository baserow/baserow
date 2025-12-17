import applicationContextMixin from '@baserow/modules/builder/mixins/applicationContext'
import elementForm from '@baserow/modules/builder/mixins/elementForm'

export default {
  mixins: [elementForm, applicationContextMixin],
  props: {
    element: {
      type: Object,
      required: true,
    },
    baseTheme: {
      type: Object,
      required: true,
    },
  },
  methods: {
    /**
     * Handles the field style changes made in the form. When the custom style form
     * is changed, this method is called with the new style values and the context
     * of the custom styles. It updates the styles of the specific field within the
     * element's fields array and returns the updated table element.
     * @param newStyleValues - The new style values to be applied to the field.
     * @param customStylesContext - The custom style context
     * @return {object} - The updated table element with the modified field styles.
     */
    onFieldStylesChanged(newStyleValues, customStylesContext) {
      const elementToUpdate = { ...this.element }
      const { styleKey } = customStylesContext
      elementToUpdate.fields = elementToUpdate.fields.map((field) => {
        if (field.id === this.defaultValues.id) {
          return {
            ...field,
            styles: { ...field.styles, [styleKey]: newStyleValues },
          }
        }
        return field
      })
      return elementToUpdate
    },
  },
}

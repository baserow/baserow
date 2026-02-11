import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  props: {
    storePrefix: {
      type: String,
      required: true,
    },
  },
  computed: {
    fieldOptions() {
      return this.$store.getters[
        `${this.storePrefix}view/form/getAllFieldOptions`
      ]
    },
  },
  methods: {
    async updateForm(values) {
      const view = this.view
      this.$store.dispatch('view/setItemLoading', { view, value: true })

      try {
        await this.$store.dispatch('view/update', {
          view,
          values,
        })
      } catch (error) {
        notifyIf(error, 'view')
      }

      this.$store.dispatch('view/setItemLoading', { view, value: false })
    },
    async updateFieldOptionsOfField(form, field, values) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/form/updateFieldOptionsOfField',
          {
            form,
            field,
            values,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async updateFieldOptionsOfFields(
      form,
      fields,
      values,
      onlyCompatible = false
    ) {
      const oldFieldOptions = clone(this.fieldOptions)
      const newFieldOptions = {}
      fields
        .filter((field) => {
          if (!onlyCompatible) {
            return true
          }
          const fieldType = this.$registry.get('field', field.type)
          return (
            Object.keys(fieldType.getFormViewFieldComponents(field, this))
              .length > 0
          )
        })
        .forEach((field) => {
          newFieldOptions[field.id] = values
        })

      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/form/updateAllFieldOptions',
          {
            form,
            newFieldOptions,
            oldFieldOptions,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}

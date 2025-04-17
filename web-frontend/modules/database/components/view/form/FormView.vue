<template>
  <div class="form-view">
    <FormViewSidebar
      :database="database"
      :table="table"
      :view="view"
      :fields="disabledFields"
      :enabled-fields="enabledFields"
      :all-fields-in-table="fields"
      :read-only="
        readOnly ||
        !$hasPermission(
          'database.table.view.update_field_options',
          view,
          database.workspace.id
        )
      "
      :store-prefix="storePrefix"
      @ordered-fields="orderFields"
      @refresh="$emit('refresh', $event)"
    ></FormViewSidebar>
    <FormViewPreview
      :database="database"
      :table="table"
      :view="view"
      :fields="enabledFields"
      :read-only="
        readOnly ||
        !$hasPermission(
          'database.table.view.update',
          view,
          database.workspace.id
        )
      "
      :store-prefix="storePrefix"
      @ordered-fields="orderFields"
    ></FormViewPreview>
  </div>
</template>

<script>
import { maxPossibleOrderValue } from '@baserow/modules/database/viewTypes'
import formViewHelpers from '@baserow/modules/database/mixins/formViewHelpers'
import FormViewSidebar from '@baserow/modules/database/components/view/form/FormViewSidebar'
import FormViewPreview from '@baserow/modules/database/components/view/form/FormViewPreview'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'FormView',
  components: { FormViewSidebar, FormViewPreview },
  mixins: [formViewHelpers],
  props: {
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    sortedFields() {
      const fields = this.fields.slice()
      return fields.sort((a, b) => {
        const orderA = this.getFieldOption(a.id, 'order', maxPossibleOrderValue)
        const orderB = this.getFieldOption(b.id, 'order', maxPossibleOrderValue)

        // First by order.
        if (orderA > orderB) {
          return 1
        } else if (orderA < orderB) {
          return -1
        }

        // Then by id.
        if (a.id < b.id) {
          return -1
        } else if (a.id > b.id) {
          return 1
        } else {
          return 0
        }
      })
    },
    disabledFields() {
      return this.sortedFields.filter((field) => !this.isFieldEnabled(field))
    },
    enabledFields() {
      return this.sortedFields.filter((field) => this.isFieldEnabled(field))
    },
  },
  methods: {
    /* Returns true if the field is enabled and not read-only. */
    isFieldEnabled(field) {
      const fieldType = this.$registry.get('field', field.type)
      return (
        this.getFieldOption(field.id, 'enabled', false) &&
        !fieldType.isReadOnlyField(field)
      )
    },
    getFieldOption(fieldId, value, fallback) {
      return this.fieldOptions[fieldId]
        ? this.fieldOptions[fieldId][value]
        : fallback
    },
    async orderFields(order) {
      // If the fields are ordered in the preview, then the disabled fields are missing
      // from the order. Because we want to preserve those order, they need to be added
      // to the end of the order to the order.
      this.disabledFields.forEach((field) => {
        if (!order.includes(field.id)) {
          order.push(field.id)
        }
      })

      // Same goes for the enabled fields. If the disabled fields are ordered, then we
      // want the enabled fields to keep the right order.
      const prepend = []
      this.enabledFields.forEach((field) => {
        if (!order.includes(field.id)) {
          prepend.push(field.id)
        }
      })
      order.unshift(...prepend)

      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/form/updateFieldOptionsOrder',
          { form: this.view, order }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>

<template>
  <div>
    <a
      ref="contextLink"
      class="header__filter-link"
      :class="{
        'active active--error': hiddenFields.length > 0,
      }"
      @click="$refs.context.toggle($refs.contextLink, 'bottom', 'left', 4)"
    >
      <i class="header__filter-icon iconoir-eye-off"></i>
      <span class="header__filter-name">{{
        $tc('gridViewHide.hideField', hiddenFields.length, {
          count: hiddenFields.length,
        })
      }}</span>
    </a>
    <ViewFieldsContext
      ref="context"
      :database="database"
      :view="view"
      :fields="fields"
      :field-options="fieldOptions"
      @update-all-field-options="updateAllFieldOptions"
      @update-field-options-of-field="updateFieldOptionsOfField"
      @update-order="orderFieldOptions"
    ></ViewFieldsContext>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ViewFieldsContext from '@baserow/modules/database/components/view/ViewFieldsContext'

export default {
  name: 'GridViewHide',
  components: { ViewFieldsContext },
  props: {
    database: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
  },
  computed: {
    hiddenFields() {
      return this.fields.filter((field) => {
        const exists = Object.prototype.hasOwnProperty.call(
          this.fieldOptions,
          field.id
        )
        return !exists || (exists && this.fieldOptions[field.id].hidden)
      })
    },
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        fieldOptions:
          this.$options.propsData.storePrefix + 'view/grid/getAllFieldOptions',
      }),
    }
  },
  methods: {
    async updateAllFieldOptions({ newFieldOptions, oldFieldOptions }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/updateAllFieldOptions',
          {
            newFieldOptions,
            oldFieldOptions,
            readOnly:
              this.readOnly ||
              !this.$hasPermission(
                'database.table.view.update_field_options',
                this.view,
                this.database.workspace.id
              ),
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async updateFieldOptionsOfField({ field, values, oldValues }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/updateFieldOptionsOfField',
          {
            field,
            values,
            oldValues,
            readOnly:
              this.readOnly ||
              !this.$hasPermission(
                'database.table.view.update_field_options',
                this.view,
                this.database.workspace.id
              ),
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async orderFieldOptions({ order }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/updateFieldOptionsOrder',
          {
            order,
            readOnly:
              this.readOnly ||
              !this.$hasPermission(
                'database.table.view.update_field_options',
                this.view,
                this.database.workspace.id
              ),
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>

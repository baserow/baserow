<template>
  <Modal ref="modal" @hidden="hidden">
    <template #actions> </template>
    <template #content>
      <div class="box__title">
        <h2 class="row-modal__title">
          {{ heading }}
        </h2>
      </div>
      <Error :error="error"></Error>
      <DefaultRowValuesForm
        v-if="fetched"
        ref="form"
        :database="database"
        :table="table"
        :view="view"
        :fields="defaultValueFields"
        :all-fields-in-table="allFieldsInTable"
        :row="row"
        :default-values="row"
        :view-default-values="viewDefaultValues"
        :read-only="readOnly"
        @submitted="handleSubmit"
      >
        <div class="actions actions--right actions--gap">
          <Button type="secondary" :disabled="saving" @click="hide">
            {{ $t('action.cancel') }}
          </Button>
          <Button type="primary" :disabled="saving" :loading="saving">
            {{ $t('defaultRowValuesModal.saveChanges') }}
          </Button>
        </div>
      </DefaultRowValuesForm>
    </template>
    <template #sidebar> </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import Error from '@baserow/modules/core/components/Error.vue'
import DefaultRowValuesForm from '@baserow/modules/database/components/view/DefaultRowValuesForm.vue'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ViewService from '@baserow/modules/database/services/view'

export default {
  name: 'DefaultRowValuesModal',
  components: {
    DefaultRowValuesForm,
    Error,
  },
  mixins: [modal, error],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: [Object, null],
      required: false,
      default: null,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['hidden'],
  data() {
    return {
      fetched: false,
      viewDefaultValues: {},
      row: {},
      saving: false,
    }
  },
  computed: {
    heading() {
      return this.$t('defaultRowValuesModal.title')
    },
    defaultValueFields() {
      return this.allFieldsInTable.filter((field) => {
        const fieldType = this.$registry.get('field', field.type)
        return fieldType.canSetDefaultViewRowValue()
      })
    },
  },
  methods: {
    async show(...args) {
      this.fetched = false
      this.hideError()
      this.getRootModal().show(...args)
      await this.fetchDefaultValues()
    },
    hidden(...args) {
      this.$emit('hidden')
    },
    buildRow() {
      this.row = Object.fromEntries(
        this.defaultValueFields.map((field) => {
          const fieldType = this.$registry.get('field', field.type)
          const defaultValue = this.viewDefaultValues[field.id]

          if (defaultValue !== undefined) {
            const convertedValue = fieldType.convertViewDefaultValue(
              field,
              defaultValue?.value
            )
            return [
              `field_${field.id}`,
              convertedValue || fieldType.getEmptyValue(field),
            ]
          }

          return [`field_${field.id}`, fieldType.getEmptyValue(field)]
        })
      )
    },
    async fetchDefaultValues() {
      try {
        const { data } = await ViewService(this.$client).fetchDefaultValues(
          this.view.id
        )
        this.viewDefaultValues = data
        this.buildRow()
        this.fetched = true
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async handleSubmit(formValues) {
      console.log({ formValues })

      this.saving = true
      this.hideError()
      try {
        const values = {}
        for (const field of this.defaultValueFields) {
          const fieldType = this.$registry.get('field', field.type)
          const value = formValues[`field_${field.id}`]
          const preparedValue = fieldType.prepareDefaultValue(field, value)
          values[field.id] = { enabled: true, value: preparedValue }
        }
        await ViewService(this.$client).updateDefaultValues(
          this.view.id,
          values
        )
        this.hide()
      } catch (error) {
        this.handleError(error, 'view')
      } finally {
        this.saving = false
      }
    },
  },
}
</script>

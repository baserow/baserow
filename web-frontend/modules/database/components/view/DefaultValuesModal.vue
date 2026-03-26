<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{ $t('defaultValuesModal.title', { name: view.name }) }}
    </h2>
    <Error :error="error"></Error>
    <div v-if="loading" class="loading"></div>
    <div v-else>
      <div
        v-for="field in editableFields"
        :key="field.id"
        class="control margin-bottom-2"
      >
        <label class="control__label control__label--small">
          <i :class="field._.type.iconClass"></i>
          {{ field.name }}
        </label>
        <div v-if="!isFieldEnabled(field.id)">
          <a @click="enableField(field)">
            {{ $t('defaultValuesModal.setDefaultValue') }}
          </a>
        </div>
        <div v-else>
          <div
            v-if="getFieldFunctions(field).length > 0"
            class="margin-bottom-1"
          >
            <RadioButton
              v-model="fieldModes[field.id]"
              value="static"
              @input="onModeChange(field)"
            >
              {{ $t('defaultValuesModal.staticValue') }}
            </RadioButton>
            <RadioButton
              v-for="func in getFieldFunctions(field)"
              :key="func.name"
              v-model="fieldModes[field.id]"
              :value="func.name"
              @input="onModeChange(field)"
            >
              {{ func.label }}
            </RadioButton>
          </div>
          <component
            :is="getFieldComponent(field)"
            v-if="fieldModes[field.id] === 'static'"
            ref="fieldComponents"
            :slug="false"
            :field="field"
            :value="rowValues[`field_${field.id}`]"
            :read-only="false"
            @update="updateFieldValue(field, $event)"
          />
          <div>
            <a class="color-error" @click="disableField(field)">
              {{ $t('defaultValuesModal.removeDefaultValue') }}
            </a>
          </div>
        </div>
      </div>
      <div class="actions">
        <div class="align-right">
          <Button
            type="primary"
            size="large"
            :loading="saving"
            :disabled="saving"
            @click="save()"
          >
            {{ $t('action.save') }}
          </Button>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import { mapGetters } from 'vuex'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import ViewService from '@baserow/modules/database/services/view'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'DefaultValuesModal',
  mixins: [modal, error],
  props: {
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
  },
  data() {
    return {
      loading: false,
      saving: false,
      enabledFieldIds: [],
      rowValues: {},
      fieldModes: {},
      fieldFunctions: {},
    }
  },
  computed: {
    ...mapGetters({
      allFields: 'field/getAll',
    }),
    editableFields() {
      return this.allFields.filter((field) => {
        const fieldType = this.$registry.get('field', field.type)
        return !fieldType.isReadOnlyField(field)
      })
    },
  },
  methods: {
    show(...args) {
      this.initializeFromView()
      return modal.methods.show.call(this, ...args)
    },
    initializeFromView() {
      const defaultValues = this.view.default_row_values
      this.enabledFieldIds = []
      this.rowValues = {}
      this.fieldModes = {}
      this.fieldFunctions = {}

      if (defaultValues) {
        this.enabledFieldIds = [...defaultValues.enabled_field_ids]
        this.rowValues = { ...defaultValues.values }
        for (const [fieldId, funcName] of Object.entries(
          defaultValues.functions || {}
        )) {
          this.fieldFunctions[fieldId] = funcName
          this.fieldModes[parseInt(fieldId)] = funcName
        }
      }

      // Set default mode to 'static' for enabled fields without a function.
      for (const fieldId of this.enabledFieldIds) {
        if (!this.fieldModes[fieldId]) {
          this.fieldModes[fieldId] = 'static'
        }
      }
    },
    isFieldEnabled(fieldId) {
      return this.enabledFieldIds.includes(fieldId)
    },
    enableField(field) {
      this.enabledFieldIds.push(field.id)
      const fieldType = this.$registry.get('field', field.type)
      this.rowValues[`field_${field.id}`] = fieldType.getEmptyValue(field)
      this.fieldModes[field.id] = 'static'
    },
    disableField(field) {
      this.enabledFieldIds = this.enabledFieldIds.filter(
        (id) => id !== field.id
      )
      delete this.rowValues[`field_${field.id}`]
      delete this.fieldModes[field.id]
      delete this.fieldFunctions[String(field.id)]
    },
    onModeChange(field) {
      const mode = this.fieldModes[field.id]
      if (mode === 'static') {
        delete this.fieldFunctions[String(field.id)]
      } else {
        this.fieldFunctions[String(field.id)] = mode
      }
    },
    getFieldFunctions(field) {
      const fieldType = this.$registry.get('field', field.type)
      if (typeof fieldType.getSupportedDefaultValueFunctions === 'function') {
        return fieldType.getSupportedDefaultValueFunctions()
      }
      return []
    },
    getFieldComponent(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.getRowEditFieldComponent(field)
    },
    updateFieldValue(field, value) {
      this.rowValues[`field_${field.id}`] = value
    },
    async save() {
      this.saving = true
      this.hideError()

      try {
        // Prepare the values for the API request using each field type's
        // prepareValueForUpdate, the same way row updates do it.
        const preparedValues = {}
        this.editableFields.forEach((field) => {
          const name = `field_${field.id}`
          if (Object.prototype.hasOwnProperty.call(this.rowValues, name)) {
            const fieldType = this.$registry.get('field', field.type)
            preparedValues[name] = fieldType.prepareValueForUpdate(
              field,
              this.rowValues[name]
            )
          }
        })

        const { data } = await ViewService(this.$client).updateDefaultValues(
          this.view.id,
          {
            values: preparedValues,
            enabledFieldIds: this.enabledFieldIds,
            functions: this.fieldFunctions,
          }
        )

        // Update the view's default_row_values in the store.
        await this.$store.dispatch('view/forceUpdate', {
          view: this.view,
          values: { default_row_values: data },
        })

        this.hide()
      } catch (err) {
        this.handleError(err, 'view')
        notifyIf(err, 'view')
      } finally {
        this.saving = false
      }
    },
  },
}
</script>

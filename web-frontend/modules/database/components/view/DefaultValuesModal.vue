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
              class="margin-left-1"
              @input="onModeChange(field)"
            >
              {{ func.label }}
            </RadioButton>
          </div>
          <component
            :is="getFieldComponent(field)"
            v-if="fieldModes[field.id] === 'static'"
            :ref="'field-' + field.id"
            :slug="false"
            :field="field"
            :value="rowValues[`field_${field.id}`]"
            :read-only="false"
            :workspace-id="database.workspace.id"
            :row="rowValues"
            :all-fields-in-table="allFields"
            @update="updateFieldValue(field, $event)"
          />
          <div class="margin-top-1">
            <a @click="disableField(field)">
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
    storePrefix: {
      type: String,
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
      const viewType = this.$registry.get('view', this.view.type)
      const visibleFields = viewType.getVisibleFieldsInOrder(
        this,
        this.allFields,
        this.view,
        this.storePrefix
      )

      const visibleFieldIds = new Set(visibleFields.map((f) => f.id))
      const hiddenFields = this.allFields.filter(
        (f) => !visibleFieldIds.has(f.id)
      )

      return [...visibleFields, ...hiddenFields].filter((field) => {
        const fieldType = this.$registry.get('field', field.type)
        return (
          !fieldType.isReadOnlyField(field) && fieldType.canBeDefaultValue()
        )
      })
    },
  },
  methods: {
    show(...args) {
      this.initializeFromView()
      return modal.methods.show.call(this, ...args)
    },
    initializeFromView() {
      const items = this.view.default_row_values || []
      this.enabledFieldIds = []
      this.rowValues = {}
      this.fieldModes = {}
      this.fieldFunctions = {}

      const itemsByFieldId = {}
      for (const item of items) {
        itemsByFieldId[item.field] = item
      }

      // Initialize every editable field with its empty value, then
      // override with the stored default if one exists.
      for (const field of this.editableFields) {
        const fieldType = this.$registry.get('field', field.type)
        const name = `field_${field.id}`
        this.rowValues[name] = fieldType.getEmptyValue(field)

        const item = itemsByFieldId[field.id]
        if (!item) {
          continue
        }

        if (item.enabled) {
          this.enabledFieldIds.push(field.id)
        }

        if (
          item.value != null &&
          (!item.field_type || item.field_type === field.type)
        ) {
          this.rowValues[name] = fieldType.parseDefaultRowValue(
            field,
            item.value
          )
        }

        const supportedFunctions = fieldType
          .getSupportedDefaultValueFunctions()
          .map((f) => f.name)
        if (item.function && supportedFunctions.includes(item.function)) {
          this.fieldFunctions[String(field.id)] = item.function
          this.fieldModes[field.id] = item.function
        }
      }

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
      return fieldType.getSupportedDefaultValueFunctions()
    },
    getFieldComponent(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.getRowEditFieldComponent(field)
    },
    updateFieldValue(field, value) {
      this.rowValues[`field_${field.id}`] = value
    },
    async save() {
      for (const fieldId of this.enabledFieldIds) {
        if (this.fieldModes[fieldId] !== 'static') {
          continue
        }
        const ref = this.$refs['field-' + fieldId]
        const component = Array.isArray(ref) ? ref[0] : ref
        if (component && !component.isValid()) {
          component.$el.scrollIntoView({ behavior: 'smooth', block: 'start' })
          return
        }
      }

      this.saving = true
      this.hideError()

      try {
        const items = this.enabledFieldIds.map((fieldId) => {
          const field = this.editableFields.find((f) => f.id === fieldId)
          const name = `field_${fieldId}`
          const funcName = this.fieldFunctions[String(fieldId)] || null

          let value = null
          if (
            field &&
            !funcName &&
            Object.prototype.hasOwnProperty.call(this.rowValues, name)
          ) {
            const fieldType = this.$registry.get('field', field.type)
            value = fieldType.prepareValueForUpdate(field, this.rowValues[name])
          }

          return {
            field: fieldId,
            enabled: true,
            value,
            function: funcName,
          }
        })

        const { data } = await ViewService(this.$client).updateDefaultValues(
          this.view.id,
          items
        )

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

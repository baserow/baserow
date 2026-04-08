<template>
  <div v-if="filteredFields.length > 0" class="restricted-view-filter-context">
    <Expandable card toggle-on-click>
      <template #header="{ expanded }">
        <div class="restricted-view-filter-context__head">
          <div class="restricted-view-filter-context__icon">
            <i
              :class="
                matches
                  ? 'iconoir-check-circle restricted-view-filter-context__icon--success'
                  : 'iconoir-warning-triangle restricted-view-filter-context__icon--warning'
              "
            ></i>
          </div>
          <div class="restricted-view-filter-context__text">
            <div class="restricted-view-filter-context__title">
              {{
                matches
                  ? $t('restrictedViewFilterContext.matchTitle')
                  : $t('restrictedViewFilterContext.mismatchTitle')
              }}
            </div>
            <div class="restricted-view-filter-context__subtitle">
              {{
                matches
                  ? $t('restrictedViewFilterContext.matchSubtitle')
                  : $t('restrictedViewFilterContext.mismatchSubtitle')
              }}
            </div>
          </div>
          <i
            class="restricted-view-filter-context__toggle"
            :class="
              expanded ? 'iconoir-nav-arrow-up' : 'iconoir-nav-arrow-down'
            "
          ></i>
        </div>
      </template>
      <div class="restricted-view-filter-context__body">
        <div
          v-for="field in filteredFields"
          :key="field.id"
          class="restricted-view-filter-context__field"
        >
          <div class="restricted-view-filter-context__field-label">
            <i
              :class="field._.type.iconClass"
              class="restricted-view-filter-context__field-icon"
            ></i>
            {{ field.name }}
          </div>
          <div class="restricted-view-filter-context__field-input">
            <div
              v-if="getFieldFunctions(field).length > 0"
              class="margin-bottom-1"
            >
              <RadioButton
                :model-value="fieldModes[field.id]"
                value="static"
                @input="onModeChange(field, 'static')"
              >
                {{ $t('defaultValuesModal.staticValue') }}
              </RadioButton>
              <RadioButton
                v-for="func in getFieldFunctions(field)"
                :key="func.name"
                :model-value="fieldModes[field.id]"
                :value="func.name"
                class="margin-left-1"
                @input="onModeChange(field, func.name)"
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
              :value="defaultViewRowValues[`field_${field.id}`]"
              :read-only="readOnly"
              :workspace-id="database.workspace.id"
              :row="defaultViewRowValues"
              :all-fields-in-table="fields"
              @update="onFieldUpdate(field, $event)"
            />
          </div>
        </div>
      </div>
    </Expandable>
  </div>
</template>

<script>
import debounce from 'lodash/debounce'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { matchSearchFilters } from '@baserow/modules/database/utils/view'
import ViewService from '@baserow/modules/database/services/view'

export default {
  name: 'RestrictedViewFilterContext',
  props: {
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      defaultViewRowValues: {},
      fieldModes: {},
      oldDefaultViewRowValues: null,
      oldFieldModes: null,
      saving: false,
      saveQueued: false,
    }
  },
  computed: {
    filteredFieldIds() {
      const ids = new Set()
      for (const filter of this.view.filters) {
        ids.add(filter.field)
      }
      return ids
    },
    filteredFields() {
      return this.fields.filter((field) => {
        if (!this.filteredFieldIds.has(field.id)) return false
        const fieldType = this.$registry.get('field', field.type)
        return fieldType.canBeDefaultValue()
      })
    },
    // Build a values object that resolves functions to their actual values,
    // so that matchSearchFilters can check them against the filters.
    resolvedDefaultViewRowValues() {
      const resolved = {}
      for (const field of this.filteredFields) {
        const name = `field_${field.id}`
        const mode = this.fieldModes[field.id]
        if (mode && mode !== 'static') {
          const fieldType = this.$registry.get('field', field.type)
          resolved[name] = fieldType.resolveDefaultValueFunction(mode, field)
        } else {
          resolved[name] = this.defaultViewRowValues[name]
        }
      }
      return resolved
    },
    matches() {
      return matchSearchFilters(
        this.$registry,
        this.view.filter_type,
        this.view.filters,
        this.view.filter_groups,
        this.fields,
        this.resolvedDefaultViewRowValues
      )
    },
  },
  watch: {
    'view.default_row_values': {
      handler() {
        // Don't overwrite local edits while a save is in flight or queued.
        if (!this.saving && !this.saveQueued) {
          this.parseDefaultValues()
        }
      },
      deep: true,
    },
    'view.filters': {
      handler() {
        if (!this.saving && !this.saveQueued) {
          this.parseDefaultValues()
        }
      },
      deep: true,
    },
  },
  created() {
    this.parseDefaultValues()
    this.debouncedSave = debounce(this.save, 400)
  },
  beforeUnmount() {
    // Flush any pending debounced save so edits aren't lost when the filter context
    // menu is removed.
    this.debouncedSave.flush()
  },
  methods: {
    parseDefaultValues() {
      const items = this.view.default_row_values || []
      const itemsByFieldId = {}
      for (const item of items) {
        itemsByFieldId[item.field] = item
      }

      const newValues = {}
      const newModes = {}
      for (const field of this.filteredFields) {
        const fieldType = this.$registry.get('field', field.type)
        const name = `field_${field.id}`
        newValues[name] = fieldType.getEmptyValue(field)
        newModes[field.id] = 'static'

        const item = itemsByFieldId[field.id]
        if (!item || !item.enabled) {
          continue
        }

        if (
          item.value != null &&
          (!item.field_type || item.field_type === field.type)
        ) {
          newValues[name] = fieldType.parseDefaultRowValue(field, item.value)
        }

        const supportedFunctions = fieldType
          .getSupportedDefaultValueFunctions()
          .map((f) => f.name)
        if (item.function && supportedFunctions.includes(item.function)) {
          newModes[field.id] = item.function
        }
      }
      this.defaultViewRowValues = newValues
      this.fieldModes = newModes
    },
    getFieldComponent(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.getRowEditFieldComponent(field)
    },
    getFieldFunctions(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.getSupportedDefaultValueFunctions()
    },
    onModeChange(field, mode) {
      if (!this.oldDefaultViewRowValues) {
        this.oldDefaultViewRowValues = { ...this.defaultViewRowValues }
        this.oldFieldModes = { ...this.fieldModes }
      }
      this.fieldModes = { ...this.fieldModes, [field.id]: mode }
      this.debouncedSave()
    },
    onFieldUpdate(field, value) {
      if (!this.oldDefaultViewRowValues) {
        this.oldDefaultViewRowValues = { ...this.defaultViewRowValues }
        this.oldFieldModes = { ...this.fieldModes }
      }
      this.defaultViewRowValues = {
        ...this.defaultViewRowValues,
        [`field_${field.id}`]: value,
      }
      this.debouncedSave()
    },
    async save() {
      if (this.saving) {
        this.saveQueued = true
        return
      }
      this.saving = true

      // Capture the local state we're about to send so we can detect if more
      // edits arrived while the request was in flight.
      const sentValues = { ...this.defaultViewRowValues }
      const sentModes = { ...this.fieldModes }

      try {
        // Preserve existing default values for non-filtered fields, only
        // overwrite the entries for fields that are currently being filtered on.
        const itemsByFieldId = new Map(
          (this.view.default_row_values || []).map((item) => [item.field, item])
        )
        this.filteredFields.forEach((field) => {
          const fieldType = this.$registry.get('field', field.type)
          const mode = sentModes[field.id]
          const funcName = mode !== 'static' ? mode : null

          let value = null
          if (!funcName) {
            value = fieldType.prepareValueForUpdate(
              field,
              sentValues[`field_${field.id}`]
            )
          }

          itemsByFieldId.set(field.id, {
            field: field.id,
            enabled: true,
            value,
            function: funcName,
          })
        })
        const items = Array.from(itemsByFieldId.values())

        const { data } = await ViewService(this.$client).updateDefaultValues(
          this.view.id,
          items
        )

        await this.$store.dispatch('view/forceUpdate', {
          view: this.view,
          values: { default_row_values: data },
        })
        // Wait for the watcher to flush so it doesn't overwrite local edits
        // that arrived while the request was in flight.
        await this.$nextTick()

        // If no further edits happened during the request, the snapshot is
        // no longer needed. Otherwise keep it for the queued save.
        if (!this.saveQueued) {
          this.oldDefaultViewRowValues = null
          this.oldFieldModes = null
        }
      } catch (err) {
        if (this.oldDefaultViewRowValues) {
          this.defaultViewRowValues = this.oldDefaultViewRowValues
          this.fieldModes = this.oldFieldModes
          this.oldDefaultViewRowValues = null
          this.oldFieldModes = null
        }
        this.saveQueued = false
        notifyIf(err, 'view')
      } finally {
        this.saving = false
        if (this.saveQueued) {
          this.saveQueued = false
          this.save()
        }
      }
    },
  },
}
</script>

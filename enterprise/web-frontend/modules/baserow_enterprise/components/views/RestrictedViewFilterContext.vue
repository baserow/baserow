<template>
  <div v-if="visibleFields.length > 0" class="restricted-view-filter-context">
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
          v-for="field in visibleFields"
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
            <div
              v-if="canRemoveDefaultValue(field)"
              class="flex align-items-center margin-top-1"
              style="--gap: 4px"
            >
              <a
                class="restricted-view-filter-context__remove"
                @click.prevent="removeDefaultValue(field)"
              >
                {{ $t('restrictedViewFilterContext.removeDefaultValue') }}
              </a>
              <HelpIcon
                :tooltip="
                  $t('restrictedViewFilterContext.removeDefaultValueHelper')
                "
                tooltip-content-type="plain"
                :tooltip-content-classes="[
                  'tooltip__content--expandable',
                  'tooltip__content--expandable-plain-text',
                ]"
                icon="info-empty"
              />
            </div>
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
import { clone } from '@baserow/modules/core/utils/object'

/**
 * Builds the API payload from a default_row_values snapshot, applying local
 * overrides (value/mode changes and removals) on top.
 */
function buildPayload(baseItems, overrides, removedFieldIds) {
  const itemsByFieldId = new Map(baseItems.map((item) => [item.field, item]))
  for (const fieldId of removedFieldIds) {
    itemsByFieldId.delete(fieldId)
  }
  for (const override of overrides) {
    itemsByFieldId.set(override.field, override)
  }
  return Array.from(itemsByFieldId.values())
}

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
      // Local UI state derived from view.default_row_values.
      defaultViewRowValues: {},
      fieldModes: {},
      removedFieldIds: [],
      // Snapshot of view.default_row_values taken before the first local edit
      // in a batch. Used to revert if the in-flight request fails.
      requestSnapshot: null,
      // Snapshot taken when edits arrive while a request is in flight. If the
      // in-flight request succeeds, this becomes the new requestSnapshot for
      // the queued save.
      pendingSnapshot: null,
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
    enabledDefaultFieldIds() {
      const ids = new Set()
      for (const item of this.view.default_row_values || []) {
        if (item.enabled) {
          ids.add(item.field)
        }
      }
      return ids
    },
    // Fields that are either used in a filter or have an enabled default value,
    // excluding fields the user has locally removed.
    visibleFields() {
      return this.fields.filter((field) => {
        if (this.removedFieldIds.includes(field.id)) return false
        if (
          !this.filteredFieldIds.has(field.id) &&
          !this.enabledDefaultFieldIds.has(field.id)
        ) {
          return false
        }
        const fieldType = this.$registry.get('field', field.type)
        return (
          !fieldType.isReadOnlyField(field) && fieldType.canBeDefaultValue()
        )
      })
    },
    // Build a values object that resolves functions to their actual values,
    // so that matchSearchFilters can check them against the filters. Includes
    // all filtered fields (even read-only ones that aren't editable) so the
    // filter matching doesn't hit undefined values.
    resolvedDefaultViewRowValues() {
      const resolved = {}
      for (const field of this.fields) {
        if (
          !this.filteredFieldIds.has(field.id) &&
          !this.fieldModes[field.id]
        ) {
          continue
        }
        const name = `field_${field.id}`
        const mode = this.fieldModes[field.id]
        if (mode && mode !== 'static') {
          const fieldType = this.$registry.get('field', field.type)
          resolved[name] = fieldType.resolveDefaultValueFunction(mode, field)
        } else {
          const fieldType = this.$registry.get('field', field.type)
          resolved[name] =
            this.defaultViewRowValues[name] ?? fieldType.getEmptyValue(field)
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
      for (const field of this.fields) {
        if (
          !this.filteredFieldIds.has(field.id) &&
          !itemsByFieldId[field.id]?.enabled
        ) {
          continue
        }
        const fieldType = this.$registry.get('field', field.type)
        if (fieldType.isReadOnlyField(field) || !fieldType.canBeDefaultValue())
          continue

        const name = `field_${field.id}`
        newValues[name] = fieldType.getEmptyValue(field)
        newModes[field.id] = 'static'

        const item = itemsByFieldId[field.id]
        if (!item || !item.enabled) continue

        if (item.value != null && item.field_type === field.type) {
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
      this.removedFieldIds = []
    },
    getFieldComponent(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.getRowEditFieldComponent(field)
    },
    getFieldFunctions(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.getSupportedDefaultValueFunctions()
    },
    canRemoveDefaultValue(field) {
      return (
        !this.readOnly &&
        !this.filteredFieldIds.has(field.id) &&
        this.enabledDefaultFieldIds.has(field.id)
      )
    },
    /**
     * Takes a snapshot of view.default_row_values before the first local edit.
     * If a request is already in flight, the snapshot goes into pendingSnapshot
     * (so that a queued save can use it). Otherwise it goes into requestSnapshot.
     */
    snapshotBeforeEdit() {
      if (this.saving) {
        if (!this.pendingSnapshot) {
          this.pendingSnapshot = clone(this.view.default_row_values || [])
        }
      } else if (!this.requestSnapshot) {
        this.requestSnapshot = clone(this.view.default_row_values || [])
      }
    },
    removeDefaultValue(field) {
      this.snapshotBeforeEdit()
      this.removedFieldIds = [...this.removedFieldIds, field.id]
      const newValues = { ...this.defaultViewRowValues }
      delete newValues[`field_${field.id}`]
      this.defaultViewRowValues = newValues
      const newModes = { ...this.fieldModes }
      delete newModes[field.id]
      this.fieldModes = newModes
      this.debouncedSave()
    },
    onModeChange(field, mode) {
      this.snapshotBeforeEdit()
      this.fieldModes = { ...this.fieldModes, [field.id]: mode }
      this.debouncedSave()
    },
    onFieldUpdate(field, value) {
      this.snapshotBeforeEdit()
      this.defaultViewRowValues = {
        ...this.defaultViewRowValues,
        [`field_${field.id}`]: value,
      }
      this.debouncedSave()
    },
    /**
     * Builds the list of local overrides from the current UI state for fields
     * that are visible (not removed).
     */
    buildOverrides() {
      return this.visibleFields.map((field) => {
        const fieldType = this.$registry.get('field', field.type)
        const mode = this.fieldModes[field.id]
        const funcName = mode && mode !== 'static' ? mode : null

        let value = null
        if (!funcName) {
          value = fieldType.prepareValueForUpdate(
            field,
            this.defaultViewRowValues[`field_${field.id}`]
          )
        }
        return {
          field: field.id,
          enabled: true,
          value,
          function: funcName,
        }
      })
    },
    async save() {
      if (this.saving) {
        this.saveQueued = true
        return
      }
      this.saving = true

      const overrides = this.buildOverrides()
      const removedIds = [...this.removedFieldIds]
      const baseItems = clone(this.view.default_row_values || [])

      try {
        const items = buildPayload(baseItems, overrides, removedIds)
        const { data } = await ViewService(this.$client).updateDefaultValues(
          this.view.id,
          items
        )

        await this.$store.dispatch('view/forceUpdate', {
          view: this.view,
          values: { default_row_values: data },
        })
        await this.$nextTick()

        if (this.saveQueued) {
          // More edits arrived during the request. The pendingSnapshot
          // becomes the requestSnapshot for the next save.
          this.requestSnapshot = this.pendingSnapshot
          this.pendingSnapshot = null
        } else {
          this.requestSnapshot = null
          this.pendingSnapshot = null
          this.removedFieldIds = []
        }
      } catch (err) {
        // Revert to the snapshot taken before the edits that triggered this
        // save, cancel any queued save, and re-parse from it.
        this.debouncedSave.cancel()
        this.saveQueued = false
        if (this.requestSnapshot) {
          await this.$store.dispatch('view/forceUpdate', {
            view: this.view,
            values: { default_row_values: this.requestSnapshot },
          })
        }
        this.requestSnapshot = null
        this.pendingSnapshot = null
        this.parseDefaultValues()
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

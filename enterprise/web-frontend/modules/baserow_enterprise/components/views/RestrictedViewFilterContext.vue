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
            <component
              :is="getFieldComponent(field)"
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
      oldDefaultViewRowValues: null,
      saving: false,
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
    matches() {
      return matchSearchFilters(
        this.$registry,
        this.view.filter_type,
        this.view.filters,
        this.view.filter_groups,
        this.fields,
        this.defaultViewRowValues
      )
    },
  },
  watch: {
    'view.default_row_values': {
      handler() {
        this.parseDefaultValues()
      },
      deep: true,
    },
    'view.filters': {
      handler() {
        this.parseDefaultValues()
      },
      deep: true,
    },
  },
  created() {
    this.parseDefaultValues()
    this.debouncedSave = debounce(this.save, 2000)
  },
  methods: {
    parseDefaultValues() {
      const items = this.view.default_row_values || []
      const itemsByFieldId = {}
      for (const item of items) {
        itemsByFieldId[item.field] = item
      }

      const newValues = {}
      for (const field of this.filteredFields) {
        const fieldType = this.$registry.get('field', field.type)
        const name = `field_${field.id}`
        newValues[name] = fieldType.getEmptyValue(field)

        const item = itemsByFieldId[field.id]
        if (
          item &&
          item.enabled &&
          item.value != null &&
          (!item.field_type || item.field_type === field.type)
        ) {
          newValues[name] = fieldType.parseDefaultRowValue(field, item.value)
        }
      }
      this.defaultViewRowValues = newValues
    },
    getFieldComponent(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.getRowEditFieldComponent(field)
    },
    onFieldUpdate(field, value) {
      if (!this.oldDefaultViewRowValues) {
        this.oldDefaultViewRowValues = { ...this.defaultViewRowValues }
      }
      this.defaultViewRowValues = {
        ...this.defaultViewRowValues,
        [`field_${field.id}`]: value,
      }
      this.debouncedSave()
    },
    async save() {
      if (this.saving) return
      this.saving = true

      try {
        const items = this.filteredFields.map((field) => {
          const fieldType = this.$registry.get('field', field.type)
          const value = fieldType.prepareValueForUpdate(
            field,
            this.defaultViewRowValues[`field_${field.id}`]
          )
          return {
            field: field.id,
            enabled: true,
            value,
            function: null,
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
        this.oldDefaultViewRowValues = null
      } catch (err) {
        if (this.oldDefaultViewRowValues) {
          this.defaultViewRowValues = this.oldDefaultViewRowValues
          this.oldDefaultViewRowValues = null
        }
        notifyIf(err, 'view')
      } finally {
        this.saving = false
      }
    },
  },
}
</script>

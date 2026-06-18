<template>
  <div
    class="grid-view__group-by-banner"
    :class="{ 'grid-view__group-by-banner--collapsed': item.collapsed }"
    :style="{
      top: item.y + 'px',
      height: item.height + 'px',
      width: width + 'px',
    }"
    :data-depth="item.depth"
    :data-collapsed="item.collapsed ? 'true' : 'false'"
  >
    <template v-if="includeRowDetails">
      <div
        class="grid-view__group-by-banner-chevron-lane"
        :style="{
          width: rowDetailsWidth + 'px',
          paddingLeft: indentPx + 'px',
        }"
      >
        <button
          type="button"
          class="grid-view__group-by-banner-toggle"
          :aria-expanded="!item.collapsed"
          :aria-label="
            item.collapsed
              ? $t('gridViewGroupByBanner.expandGroup')
              : $t('gridViewGroupByBanner.collapseGroup')
          "
          @click="$emit('toggle', item.path)"
        >
          <i
            :class="
              item.collapsed
                ? 'iconoir-nav-arrow-right'
                : 'iconoir-nav-arrow-down'
            "
          />
        </button>
      </div>
      <div
        v-if="primaryFieldWidth > 0"
        class="grid-view__group-by-banner-primary"
        :style="{ width: primaryFieldWidth + 'px' }"
      >
        <div class="grid-view__group-by-banner-stack">
          <div class="grid-view__group-by-banner-label">
            {{ fieldNameLabel }}
          </div>
          <div class="grid-view__group-by-banner-value">
            <span
              v-if="isEmptyValue"
              class="grid-view__group-by-banner-value-empty"
            >
              {{ emptyValueLabel }}
            </span>
            <component
              :is="groupByComponent"
              v-else-if="groupByComponent"
              :field="groupByField"
              :value="rowValueForGroup"
              :workspace-id="workspaceId"
            />
            <span v-else class="grid-view__group-by-banner-value-text">
              {{ fallbackValueText }}
            </span>
          </div>
        </div>
        <div class="grid-view__group-by-banner-count">
          {{ item.rowCount }}
        </div>
      </div>
    </template>
  </div>
</template>

<script>
const DEPTH_INDENT_PX = 24
const BASE_CHEVRON_GUTTER = 12

export default {
  name: 'GridViewGroupByBanner',
  props: {
    item: {
      type: Object,
      required: true,
    },
    groupByFields: {
      type: Array,
      required: true,
    },
    includeRowDetails: {
      type: Boolean,
      default: false,
    },
    primaryFieldWidth: {
      type: Number,
      default: 0,
    },
    rowDetailsWidth: {
      type: Number,
      default: 72,
    },
    workspaceId: {
      type: null,
      default: null,
    },
    width: {
      type: Number,
      required: true,
    },
  },
  emits: ['toggle'],
  computed: {
    groupByField() {
      return this.groupByFields[this.item.depth]
    },
    fieldType() {
      if (!this.groupByField) {
        return null
      }
      return this.$registry.get('field', this.groupByField.type)
    },
    fieldNameLabel() {
      return (this.groupByField?.name || '').toUpperCase()
    },
    groupValue() {
      const field = this.groupByField
      if (!field) {
        return null
      }
      return this.item.path[`field_${field.id}`]
    },
    rowValueForGroup() {
      const field = this.groupByField
      if (!field || !this.fieldType) {
        return null
      }
      const baseValue = this.fieldType.getRowValueFromGroupValue(
        field,
        this.groupValue
      )
      const options = field.select_options
      if (!Array.isArray(options)) {
        return baseValue
      }

      if (
        baseValue &&
        typeof baseValue === 'object' &&
        !Array.isArray(baseValue) &&
        'id' in baseValue
      ) {
        const full = options.find((option) => option.id === baseValue.id)
        return full ? { ...full } : baseValue
      }
      if (Array.isArray(baseValue)) {
        return baseValue.map((value) => {
          const id =
            typeof value === 'object' && value !== null ? value.id : value
          const full = options.find((option) => option.id === id)
          return full ? { ...full } : value
        })
      }
      return baseValue
    },
    isEmptyValue() {
      const value = this.rowValueForGroup
      return value === null || value === undefined || value === ''
    },
    emptyValueLabel() {
      return this.$t('gridViewGroupByBanner.emptyValue')
    },
    groupByComponent() {
      if (this.isEmptyValue || !this.groupByField || !this.fieldType) {
        return null
      }
      if (typeof this.fieldType.getGroupByComponent !== 'function') {
        return null
      }
      return this.fieldType.getGroupByComponent(this.groupByField)
    },
    indentPx() {
      return BASE_CHEVRON_GUTTER + this.item.depth * DEPTH_INDENT_PX
    },
    fallbackValueText() {
      const value = this.rowValueForGroup
      if (value === null || value === undefined) {
        return ''
      }
      if (typeof value === 'boolean') {
        return value ? 'true' : 'false'
      }
      if (this.fieldType?.toHumanReadableString) {
        try {
          const text = this.fieldType.toHumanReadableString(
            this.groupByField,
            value
          )
          if (typeof text === 'string') {
            return text
          }
        } catch (_) {
          // Fall back to the generic object/string rendering below.
        }
      }
      if (typeof value === 'object') {
        if ('value' in value) {
          return value.value
        }
        return JSON.stringify(value)
      }
      return String(value)
    },
  },
}
</script>

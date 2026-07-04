<template>
  <div
    class="grid-view__group-by-banner"
    :class="{
      'grid-view__group-by-banner--collapsed': item.collapsed,
      'grid-view__group-by-banner--gap-above': item.gapAbove,
    }"
    :style="{
      top: item.y + 'px',
      height: item.height + 'px',
      width: width + 'px',
    }"
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
        :style="{
          width: primaryFieldWidth + 'px',
          paddingLeft: indentPx + 'px',
        }"
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
    <div
      v-for="(position, index) in separatorPositions"
      :key="'separator-' + index"
      class="grid-view__group-by-banner-separator"
      :style="{ left: position - 1 + 'px' }"
    />
  </div>
</template>

<script>
import { groupBannerIndentPx } from '@baserow/modules/database/utils/gridGroupByRender'

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
    separatorPositions: {
      type: Array,
      default: () => [],
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
      return this.groupByField?.name || ''
    },
    groupValue() {
      const field = this.groupByField
      if (!field) {
        return null
      }
      return this.item.path[`field_${field.id}`]
    },
    displayValue() {
      const field = this.groupByField
      const display = this.item.display
      if (!field || !display) {
        return undefined
      }
      const key = `field_${field.id}`
      return key in display ? display[key] : undefined
    },
    rowValueForGroup() {
      const field = this.groupByField
      if (!field || !this.fieldType) {
        return null
      }
      // Reference fields (collaborators, link rows, selects) can't be rendered from
      // their group id(s) alone, so the backend resolves them to a renderable value
      // in `display`. Other field types group on a value that is already displayable.
      if (this.displayValue !== undefined) {
        return this.displayValue
      }
      return this.fieldType.getRowValueFromGroupValue(field, this.groupValue)
    },
    isEmptyValue() {
      const value = this.rowValueForGroup
      // Array-valued group keys (multiple select, link row, collaborators) come through
      // as an empty array when the group has no values.
      if (Array.isArray(value)) {
        return value.length === 0
      }
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
      return groupBannerIndentPx(
        this.item.depth,
        this.groupByFields.length,
        this.rowDetailsWidth
      )
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

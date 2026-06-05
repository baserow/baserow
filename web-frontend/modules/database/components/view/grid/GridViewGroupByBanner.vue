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
    :data-path="pathSerialized"
  >
    <template v-if="includeRowDetails">
      <div
        class="grid-view__group-by-banner__chevron-lane"
        :style="{
          width: rowDetailsWidth + 'px',
          paddingLeft: indentPx + 'px',
        }"
      >
        <button
          type="button"
          class="grid-view__group-by-banner__toggle"
          :aria-label="item.collapsed ? 'Expand group' : 'Collapse group'"
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
        class="grid-view__group-by-banner__primary"
        :style="{ width: primaryFieldWidth + 'px' }"
      >
        <div class="grid-view__group-by-banner__stack">
          <div class="grid-view__group-by-banner__label">
            {{ fieldNameLabel }}
          </div>
          <div class="grid-view__group-by-banner__value">
            <span
              v-if="isEmptyValue"
              class="grid-view__group-by-banner__value-empty"
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
            <span v-else class="grid-view__group-by-banner__value-text">
              {{ fallbackValueText }}
            </span>
          </div>
        </div>
        <div class="grid-view__group-by-banner__count">
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
      return '(Empty)'
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
    pathSerialized() {
      const path = {}
      for (const field of this.groupByFields) {
        const key = `field_${field.id}`
        if (key in this.item.path) {
          path[key] = this.item.path[key]
        }
      }
      return JSON.stringify(path)
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

<style lang="scss" scoped>
.grid-view__group-by-banner {
  position: absolute;
  left: 0;
  display: flex;
  align-items: stretch;
  box-sizing: border-box;
  background: #f8f8f8;
  border-bottom: 1px solid #e5e7eb;
  font-size: 13px;
}

.grid-view__group-by-banner--collapsed {
  background: #f3f3f3;
}

.grid-view__group-by-banner__chevron-lane {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  box-sizing: border-box;
}

.grid-view__group-by-banner__toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  font-size: 14px;

  &:hover {
    background: #e5e7eb;
    color: #111827;
  }
}

.grid-view__group-by-banner__primary {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  box-sizing: border-box;
  padding: 0 12px;
}

.grid-view__group-by-banner__stack {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
}

.grid-view__group-by-banner__label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #6b7280;
  line-height: 1.2;
  text-transform: uppercase;
}

.grid-view__group-by-banner__value {
  overflow: hidden;
  color: #111827;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.grid-view__group-by-banner__value-empty {
  color: #9ca3af;
  font-style: italic;
}

.grid-view__group-by-banner__count {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  min-width: 24px;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  background: #e5e7eb;
  color: #374151;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
}
</style>

<template>
  <div
    class="grid-grouped-banner"
    :class="{
      'grid-grouped-banner--collapsed': item.collapsed,
    }"
    :style="{
      top: item.y + 'px',
      height: item.height + 'px',
      width: totalWidth + 'px',
    }"
    :data-depth="item.depth"
    :data-collapsed="item.collapsed ? 'true' : 'false'"
    :data-path="pathSerialised"
  >
    <!--
      The banner is a full-width strip; its visual content (chevron,
      uppercase field label, value chip, count) lives in a fixed-width
      "primary lane" sized to the first visible field's width + the
      row-id lane width, plus the depth-driven indent. Everything
      after the primary lane is empty space that hosts per-column
      aggregations in a follow-up — for now it just lets the banner
      background extend cleanly to the right edge.
    -->
    <div
      class="grid-grouped-banner__chevron-lane"
      :style="{
        width: idLaneWidth + 'px',
        paddingLeft: indentPx + 'px',
      }"
    >
      <button
        type="button"
        class="grid-grouped-banner__toggle"
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
      class="grid-grouped-banner__primary"
      :style="{ width: primaryFieldWidth + 'px' }"
    >
      <div class="grid-grouped-banner__stack">
        <div class="grid-grouped-banner__label">{{ fieldNameLabel }}</div>
        <div class="grid-grouped-banner__value">
          <span v-if="isEmptyValue" class="grid-grouped-banner__value-empty">
            {{ emptyValueLabel }}
          </span>
          <component
            :is="cardComponent"
            v-else-if="cardComponent"
            :row="syntheticRow"
            :field="groupByField"
            :value="rowValueForCell"
            :workspace-id="workspaceId"
          />
          <span v-else class="grid-grouped-banner__value-text">{{
            fallbackValueText
          }}</span>
        </div>
      </div>
      <div class="grid-grouped-banner__count">{{ item.rowCount }}</div>
    </div>
  </div>
</template>

<script>
/**
 * A single group banner row, styled to mirror Airtable's grouped grid:
 *   - Short banner sitting in the first column lane (left-aligned).
 *   - Chevron toggle on the left for collapse/expand.
 *   - Depth-based left indent (24px per level).
 *   - Uppercase field-name label above the group value.
 *   - Group value rendered via the field type's group-value cell, so
 *     select fields show their colored chip, booleans show their
 *     icon, etc. Falls back to text/(Empty).
 *   - Row count trailing the value.
 *
 * Pure presentation: takes a `header` item from the render core and
 * emits `toggle` when the chevron is clicked. The container component
 * (`GridGrouped`) is responsible for dispatching the store mutation
 * that flips collapse state.
 */
const DEPTH_INDENT_PX = 24
const ID_LANE_WIDTH = 72
const DEFAULT_PRIMARY_WIDTH = 200
const BASE_CHEVRON_GUTTER = 12

export default {
  name: 'GridGroupedBanner',
  props: {
    item: {
      type: Object,
      required: true,
      validator: (it) => it.type === 'header',
    },
    groupByFields: {
      type: Array,
      required: true,
    },
    totalWidth: {
      // Width of the full row (ID lane + all column lanes). The
      // banner background spans this width to feel like one row in
      // the table.
      type: Number,
      default: 0,
    },
    primaryFieldWidth: {
      // Width of just the primary (first visible) field column. The
      // banner's stacked label+value + the right-aligned count fit
      // exactly inside this lane, so they line up with the first
      // body-row cell underneath.
      type: Number,
      default: DEFAULT_PRIMARY_WIDTH,
    },
    idLaneWidth: {
      // Width of the row-id / chevron lane. The chevron lives here,
      // separated from the primary content so the stacked
      // label+value column starts at the same x as the primary
      // field's body-row cells.
      type: Number,
      default: ID_LANE_WIDTH,
    },
    workspaceId: {
      // Forwarded to `RowCardField*` components which sometimes need
      // it (e.g. file thumbnails resolve against the workspace).
      type: null,
      default: null,
    },
  },
  emits: ['toggle'],
  computed: {
    groupByField() {
      // The field whose value this banner displays — depth=0 → first
      // group-by field, depth=1 → second, …
      return this.groupByFields[this.item.depth] ?? null
    },
    fieldType() {
      if (!this.groupByField) return null
      return this.$registry.get('field', this.groupByField.type)
    },
    fieldNameLabel() {
      return (this.groupByField?.name ?? '').toUpperCase()
    },
    rowValueForCell() {
      // Translate the group-form value (what's stored in `item.path`)
      // back to a row-form value, since field-type renderers expect
      // row-form. `getRowValueFromGroupValue` is the field type's
      // declared converter, but for select-type fields it only knows
      // how to reconstruct the id wrapper — the card components need
      // the full `{id, value, color}` to render the chip, which we
      // resolve here against `field.select_options`.
      if (!this.groupByField || !this.fieldType) return null
      const key = `field_${this.groupByField.id}`
      const groupValue = this.item.path[key]
      const baseValue = this.fieldType.getRowValueFromGroupValue(
        this.groupByField,
        groupValue
      )
      const options = this.groupByField.select_options
      if (!Array.isArray(options)) return baseValue
      // Single-select: baseValue = {id}
      if (
        baseValue &&
        typeof baseValue === 'object' &&
        !Array.isArray(baseValue) &&
        'id' in baseValue
      ) {
        const full = options.find((o) => o.id === baseValue.id)
        return full ? { ...full } : baseValue
      }
      // Multiple-select: baseValue = [{id}, ...] or [id, ...]
      if (Array.isArray(baseValue)) {
        return baseValue.map((v) => {
          const id = typeof v === 'object' && v !== null ? v.id : v
          const full = options.find((o) => o.id === id)
          return full ? { ...full } : v
        })
      }
      return baseValue
    },
    isEmptyValue() {
      const value = this.rowValueForCell
      return value === null || value === undefined || value === ''
    },
    emptyValueLabel() {
      return '(Empty)'
    },
    cardComponent() {
      // Reuse the same `RowCardField*` component the card view uses,
      // so each field type renders its value exactly the way it does
      // in cards: chip for single-select, comma-separated chips for
      // multi-select, checkbox for boolean, formatted date for date,
      // etc. The field-type registry's `getCardComponent` is the
      // single canonical lookup.
      if (this.isEmptyValue) return null
      if (!this.fieldType) return null
      if (typeof this.fieldType.getCardComponent !== 'function') return null
      try {
        return this.fieldType.getCardComponent(this.groupByField)
      } catch (_) {
        return null
      }
    },
    syntheticRow() {
      // `RowCardField*` components read the value from
      // `row[\`field_${id}\`]` rather than the `value` prop in some
      // implementations. Build a row-shaped object with the single
      // field populated so they render correctly even when reading
      // from `row` instead of `value`.
      if (!this.groupByField) return {}
      return { [`field_${this.groupByField.id}`]: this.rowValueForCell }
    },
    pathSerialised() {
      // Stable JSON serialisation of the group path keyed in
      // group-by-field order. Used as a `data-path` attribute so
      // e2e tests can target a specific group without poking at
      // the rendered chip text.
      const out = {}
      for (const f of this.groupByFields) {
        const key = `field_${f.id}`
        if (key in this.item.path) out[key] = this.item.path[key]
      }
      return JSON.stringify(out)
    },
    indentPx() {
      // Base 12px gutter (matches the row-id column's left padding so
      // the chevron sits at the same x as the row number underneath)
      // plus a per-level indent for nested groups.
      return BASE_CHEVRON_GUTTER + this.item.depth * DEPTH_INDENT_PX
    },
    fallbackValueText() {
      // Last-resort string for a field type that doesn't expose a
      // card component. Uses `toHumanReadableString` when available
      // (same path the grid uses for sort labels + search snippets).
      const field = this.groupByField
      const value = this.rowValueForCell
      if (value === null || value === undefined) return ''
      if (typeof value === 'boolean') return value ? '✓' : '✗'
      if (this.fieldType?.toHumanReadableString) {
        try {
          const s = this.fieldType.toHumanReadableString(field, value)
          if (typeof s === 'string') return s
        } catch (_) {
          /* fall through */
        }
      }
      if (typeof value === 'object') {
        if ('value' in value) return value.value
        return JSON.stringify(value)
      }
      return String(value)
    },
  },
}
</script>

<style lang="scss" scoped>
.grid-grouped-banner {
  position: absolute;
  left: 0;
  display: flex;
  align-items: stretch;
  background: #f8f8f8;
  border-bottom: 1px solid #e5e7eb;
  font-size: 13px;
  box-sizing: border-box;
}

.grid-grouped-banner--collapsed {
  background: #f3f3f3;
}

.grid-grouped-banner__chevron-lane {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding-left: 12px;
  box-sizing: border-box;
}

.grid-grouped-banner__toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: 0;
  border-radius: 4px;
  cursor: pointer;
  color: #6b7280;
  font-size: 14px;

  &:hover {
    background: #e5e7eb;
    color: #111827;
  }
}

.grid-grouped-banner__primary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 12px;
  box-sizing: border-box;
  flex: 0 0 auto;
}

.grid-grouped-banner__stack {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
}

.grid-grouped-banner__label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #6b7280;
  text-transform: uppercase;
  line-height: 1.2;
}

.grid-grouped-banner__value {
  font-size: 13px;
  font-weight: 500;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.2;
}

.grid-grouped-banner__value-empty {
  color: #9ca3af;
  font-style: italic;
}

.grid-grouped-banner__count {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
  height: 20px;
  min-width: 24px;
  border-radius: 999px;
  background: #e5e7eb;
  color: #374151;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  box-sizing: border-box;
}
</style>

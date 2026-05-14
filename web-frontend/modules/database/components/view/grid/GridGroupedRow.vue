<template>
  <div
    class="grid-grouped-row__wrapper"
    :style="{
      top: item.y + 'px',
      height: item.height + 'px',
      width: totalWidth + 'px',
    }"
  >
    <RecursiveWrapper
      :components="
        wrapperDecorations.map((comp) => ({
          ...comp,
          props: comp.propsFn(item.row),
        }))
      "
      first-component-class="grid-grouped-row__decoration"
    >
      <div
        class="grid-view__row grid-grouped-row"
        :class="{
          'grid-view__row--selected': isRowHighlighted,
          'grid-view__row--loading': item.row?._?.loading,
          'grid-view__row--hover': isHovering,
          'grid-view__row--warning': hasWarning,
        }"
        :style="{
          height: item.height + 'px',
          width: totalWidth + 'px',
        }"
        :data-row-id="item.row?.id"
        @mouseenter="isHovering = true"
        @mouseleave="isHovering = false"
        @contextmenu.prevent="onRowContext($event)"
      >
    <div v-if="hasWarning" class="grid-view__row-warning">
      <template v-if="!item.row?._?.matchFilters">
        {{ $t('gridViewRow.rowNotMatchingFilters') }}
      </template>
      <template v-else-if="!item.row?._?.matchSearch">
        {{ $t('gridViewRow.rowNotMatchingSearch') }}
      </template>
      <template v-else-if="!item.row?._?.matchSortings">
        {{ $t('gridViewRow.rowHasMoved') }}
      </template>
    </div>
    <div
      class="grid-view__column grid-view__column--no-border-right grid-grouped-row__id-lane"
      :style="{ width: idLaneWidth + 'px' }"
    >
      <div class="grid-view__row-info">
        <div
          v-if="isCheckboxSelected || isHovering"
          class="grid-view__row-checkbox"
        >
          <Checkbox
            :checked="isCheckboxSelected"
            :size="'small'"
            @input="toggleRowCheckbox"
          />
        </div>
        <div
          v-else
          class="grid-view__row-count"
          :class="{ 'grid-view__row-count--hide-on-hover': canDrag }"
          :title="item.row?.id"
        >
          <div class="grid-view__row-count-content">{{ item.row?.id }}</div>
        </div>
        <div
          v-if="!readOnly && canDrag"
          class="grid-view__row-drag"
          @mousedown="onRowDragMousedown($event)"
        ></div>
        <component
          :is="rowExpandButton"
          v-if="item.row && !item.row?._?.loading"
          :row="item.row"
          :workspace-id="workspaceId"
          :table="table"
          @edit-modal="onEditModal"
        ></component>
        <component
          :is="dec.component"
          v-for="dec in firstCellDecorations"
          :key="dec.decoration.id"
          v-bind="dec.propsFn(item.row)"
        />
      </div>
    </div>
    <GridViewCell
      v-for="(field, fieldIdx) in visibleFields"
      :key="'r' + item.row?.id + 'f' + field.id"
      :workspace-id="workspaceId"
      :field="field"
      :row="item.row"
      :all-fields-in-table="allFieldsInTable"
      :state="cellState"
      :multi-select-position="multiSelectPositionFor(field, fieldIdx)"
      :read-only="readOnly"
      :store-prefix="storePrefix"
      :is-selected="isCellSelected(field.id)"
      :is-alive="false"
      :style="{ width: cellWidth(field) + 'px' }"
      @cell-mousedown-left="onCellMousedown(field, fieldIdx)"
      @cell-mouseover="onCellMouseover(field, fieldIdx)"
      @cell-mouseup-left="onCellMouseup(field, fieldIdx)"
      @cell-shift-click="onCellShiftClick(field, fieldIdx)"
      @select="onCellSelect(field)"
      @unselect="onCellUnselect"
      @selected="$emit('cell-selected-presence', $event)"
      @unselected="$emit('cell-unselected-presence', $event)"
      @update="$emit('update', $event)"
      @paste="$emit('paste', $event)"
      @edit="$emit('edit', $event)"
      @refresh-row="$emit('refresh-row', $event)"
      @add-row-after="$emit('add-row-after', $event)"
    />
      </div>
    </RecursiveWrapper>
  </div>
</template>

<script>
/**
 * One body row in the grouped view, rendered with the *exact same*
 * `GridViewCell` the flat grid uses. This gives the grouped view
 * automatic parity on:
 *   - cell visuals (chip / icon / formatted text per field type)
 *   - hover / cursor (`cursor: cell`)
 *   - cell selection (click → highlight → mount the editable component)
 *   - inline editor lifecycle (text input, dropdown, datepicker, …)
 *   - paste / refresh-row events
 *
 * Multi-select coordinates and the legacy `state` object are simulated
 * with stable empty shapes — multi-select isn't wired in the grouped
 * path yet, but the cells render correctly with the placeholders and
 * we get to keep the same component without forking visuals.
 */
import { markRaw } from 'vue'

import GridViewCell from '@baserow/modules/database/components/view/grid/GridViewCell'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import RecursiveWrapper from '@baserow/modules/core/components/RecursiveWrapper'
import { computeMultiSelectPosition } from '@baserow/modules/database/utils/row'
import { GRID_VIEW_MULTI_SELECT_AREA } from '@baserow/modules/database/constants'

const DEFAULT_CELL_WIDTH = 200
const ID_LANE_WIDTH = 72

const READ_ONLY_CELL_STATE = Object.freeze({
  loading: false,
  fetching: false,
  selected: false,
  selectedFieldId: -1,
  selectedBy: [],
})

const EMPTY_MULTI_SELECT_POSITION = Object.freeze({
  row: { id: -1 },
  field: { id: -1 },
  index: -1,
  group: { isFirst: false, isLast: false },
})

export default {
  name: 'GridGroupedRow',
  components: { GridViewCell, Checkbox, RecursiveWrapper },
  data() {
    return {
      // Local hover state — flat tracks it via `row._.hover` in its
      // buffer; we don't have that buffer here so each grouped row
      // tracks its own. Same trigger for the checkbox UI: shown on
      // hover OR when selected.
      isHovering: false,
    }
  },
  props: {
    item: {
      type: Object,
      required: true,
      validator: (it) => it.type === 'row',
    },
    visibleFields: {
      type: Array,
      required: true,
    },
    fieldOptions: {
      type: Object,
      default: () => ({}),
    },
    workspaceId: {
      type: null,
      default: null,
    },
    storePrefix: {
      type: String,
      default: 'page/',
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
    canDrag: {
      type: Boolean,
      default: false,
    },
    table: {
      type: Object,
      default: null,
    },
    decorationsByPlace: {
      type: Object,
      default: () => ({}),
    },
    allFieldsInTable: {
      type: Array,
      default: () => [],
    },
    selectedCell: {
      // The single grid-wide selected cell, lifted from the
      // `gridGrouped` store via the parent container. Passing it
      // as a prop (rather than reading it from the store directly
      // here) keeps the row component dumb + cheap to instantiate.
      type: Object,
      default: null,
    },
  },
  emits: [
    'update',
    'paste',
    'edit',
    'refresh-row',
    'add-row-after',
    'cell-select',
    'cell-unselect',
    'cell-selected-presence',
    'cell-unselected-presence',
    'row-context',
    'cell-mousedown-left',
    'cell-mouseover',
    'cell-mouseup-left',
    'cell-shift-click',
    'row-dragging',
    'edit-modal',
  ],
  computed: {
    rowExpandButton() {
      return markRaw(
        this.$registry
          .get('application', 'database')
          .getRowExpandButtonComponent()
      )
    },
    firstCellDecorations() {
      return this.decorationsByPlace?.first_cell ?? []
    },
    wrapperDecorations() {
      return this.decorationsByPlace?.wrapper ?? []
    },
    cellState() {
      return READ_ONLY_CELL_STATE
    },
    emptyMultiSelectPosition() {
      return EMPTY_MULTI_SELECT_POSITION
    },
    idLaneWidth() {
      return ID_LANE_WIDTH
    },
    totalWidth() {
      const cellsWidth = this.visibleFields.reduce(
        (sum, f) => sum + this.cellWidth(f),
        0
      )
      return ID_LANE_WIDTH + cellsWidth
    },
    isRowHighlighted() {
      return false
    },
    hasWarning() {
      const meta = this.item.row?._
      if (!meta) return false
      return (
        meta.matchFilters === false ||
        meta.matchSortings === false ||
        meta.matchSearch === false
      )
    },
    isCheckboxSelected() {
      // Reuse the flat grid's checkbox selection state — single source
      // of truth for "which rows are checked" across both grids.
      const rowId = this.item.row?.id
      if (rowId == null) return false
      const ids =
        this.$store.getters[this.storePrefix + 'view/grid/getCheckboxSelectedRowsIds']
      return Array.isArray(ids) && ids.includes(rowId)
    },
    isAreaSelectionActive() {
      const selectionType =
        this.$store.getters[this.storePrefix + 'view/grid/getSelectionType']
      return (
        selectionType === GRID_VIEW_MULTI_SELECT_AREA &&
        this.$store.getters[this.storePrefix + 'view/grid/isMultiSelectActive']
      )
    },
    rowIndexInLinearisation() {
      // Position of this row in the linearised visible-row list —
      // gives us the same integer "row index" the flat grid stores
      // for its multi-select head/tail.
      const rowId = this.item.row?.id
      if (rowId == null) return -1
      return (
        this.$store.getters[
          this.storePrefix + 'view/gridGrouped/linearisedRowIndexById'
        ]?.(rowId) ?? -1
      )
    },
  },
  methods: {
    cellWidth(field) {
      const opts = this.fieldOptions[field.id]
      return opts?.width ?? DEFAULT_CELL_WIDTH
    },
    isCellSelected(fieldId) {
      const sel = this.selectedCell
      return (
        sel != null &&
        sel.rowId === this.item.row?.id &&
        sel.fieldId === fieldId
      )
    },
    onCellMousedown(field, fieldIdx) {
      // 1. Single-cell selection (container dispatches to the
      //    grouped store).
      this.$emit('cell-select', {
        rowId: this.item.row?.id,
        fieldId: field.id,
      })
      // 2. Start a potential area drag-select via the container.
      //    `GridViewCell` already routes shift+mousedown to
      //    `cell-shift-click` instead of `cell-mousedown-left`, so
      //    we don't need to check the modifier here.
      this.$emit('cell-mousedown-left', this._cellEventPayload(field, fieldIdx))
    },
    onCellMouseover(field, fieldIdx) {
      this.$emit('cell-mouseover', this._cellEventPayload(field, fieldIdx))
    },
    onCellMouseup(field, fieldIdx) {
      this.$emit('cell-mouseup-left', this._cellEventPayload(field, fieldIdx))
    },
    onCellShiftClick(field, fieldIdx) {
      this.$emit('cell-shift-click', this._cellEventPayload(field, fieldIdx))
    },
    _cellEventPayload(field, fieldIdx) {
      return {
        row: this.item.row,
        field,
        rowIndex: this.rowIndexInLinearisation,
        fieldIndex: fieldIdx,
      }
    },
    multiSelectPositionFor(field, fieldIdx) {
      const rowId = this.item.row?.id
      if (rowId == null) return EMPTY_MULTI_SELECT_POSITION
      const flatGetters = (k) =>
        this.$store.getters[this.storePrefix + 'view/grid/' + k]
      return computeMultiSelectPosition({
        isAreaSelectionActive: this.isAreaSelectionActive,
        isCheckboxSelected: this.isCheckboxSelected,
        rowIndex: this.rowIndexInLinearisation,
        fieldIndex: fieldIdx,
        rowIndexRange: flatGetters('getMultiSelectRowIndexSorted'),
        fieldIndexRange: flatGetters('getMultiSelectFieldIndexSorted'),
      })
    },
    onCellSelect(field) {
      this.$emit('cell-select', {
        rowId: this.item.row?.id,
        fieldId: field?.id,
      })
    },
    onCellUnselect() {
      this.$emit('cell-unselect')
    },
    onRowContext(event) {
      if (!this.item.row) return
      this.$emit('row-context', { row: this.item.row, event })
    },
    onRowDragMousedown(event) {
      if (!this.item.row) return
      event.preventDefault()
      this.$emit('row-dragging', { row: this.item.row, event })
    },
    onEditModal() {
      if (!this.item.row) return
      this.$emit('edit-modal', this.item.row)
    },
    toggleRowCheckbox() {
      if (!this.item.row) return
      this.$store.dispatch(
        this.storePrefix + 'view/grid/toggleCheckboxRowSelection',
        { row: this.item.row }
      )
    },
  },
}
</script>

<style lang="scss" scoped>
// Absolute-positioned shell that the layout drops at `item.y`.
// Always renders, so wrapper-place decorations (full-row background
// fill, etc.) have a stable mount point regardless of the
// `RecursiveWrapper` collapse behaviour when no decorations are
// active. The shell delegates background/hover/selected styling to
// the inner `.grid-grouped-row`.
.grid-grouped-row__wrapper {
  position: absolute;
  left: 0;
}

.grid-grouped-row {
  border-bottom: 1px solid #f0f0f0;
  // Inherit the flat grid's row appearance (background, hover,
  // selected, warning states) by reusing the `.grid-view__row` class
  // on the root.
}

.grid-grouped-row__id-lane {
  flex: 0 0 auto;
}
</style>

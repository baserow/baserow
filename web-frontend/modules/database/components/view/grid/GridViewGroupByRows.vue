<template>
  <div class="grid-view__group-by-rows" :style="{ height: totalHeight + 'px' }">
    <template v-for="item in visibleItems" :key="itemKey(item)">
      <GridViewGroupByBanner
        v-if="item.type === 'header'"
        :item="item"
        :group-by-fields="groupByFields"
        :include-row-details="includeRowDetails"
        :row-details-width="gridViewRowDetailsWidth"
        :workspace-id="workspaceId"
        :width="sectionWidth"
        :visible-fields="visibleFields"
        :field-widths="fieldWidths"
        :view="view"
        :store-prefix="storePrefix"
        @toggle="toggleGroup"
        @aggregation-changed="onAggregationChanged"
      />
      <div
        v-else-if="item.type === 'row' && shouldRenderRows"
        class="grid-view__group-by-rows-row"
        :class="rowClass(item.row)"
        :style="{
          top: item.y + 'px',
          transform: `translateX(${leftOffset || 0}px)`,
        }"
      >
        <GridViewRow
          :view="view"
          :workspace-id="workspaceId"
          :row="item.row"
          :rendered-fields="renderedFields"
          :visible-fields="visibleFields"
          :all-visible-fields="allVisibleFields"
          :all-fields-in-table="allFieldsInTable"
          :field-widths="fieldWidths"
          :include-row-details="includeRowDetails"
          :include-group-by="false"
          :decorations-by-place="decorationsByPlace"
          :read-only="readOnly"
          :can-drag="false"
          :focus-entries-by-cell="focusEntriesByCell"
          :focus-entries-by-row="focusEntriesByRow"
          :store-prefix="storePrefix"
          :row-identifier-type="view.row_identifier_type"
          :count="item.globalRowOffset + 1"
          @editing-changed="$emit('editing-changed', $event)"
          @update="$emit('update', $event)"
          @paste="$emit('paste', $event)"
          @edit="$emit('edit', $event)"
          @cell-mousedown-left="$emit('cell-mousedown-left', $event)"
          @cell-mouseover="$emit('cell-mouseover', $event)"
          @cell-mouseup-left="$emit('cell-mouseup-left', $event)"
          @cell-shift-click="$emit('cell-shift-click', $event)"
          @cell-selected="$emit('cell-selected', $event)"
          @selected="$emit('selected', $event)"
          @unselected="$emit('unselected', $event)"
          @select="$emit('select', $event)"
          @unselect="$emit('unselect', $event)"
          @select-next="$emit('select-next', $event)"
          @add-row-after="$emit('add-row-after', $event)"
          @edit-modal="$emit('edit-modal', $event)"
          @refresh-row="$emit('refresh-row', $event)"
          @row-dragging="$emit('row-dragging', $event)"
          @row-hover="$emit('row-hover', $event)"
          @row-context="$emit('row-context', $event)"
        />
      </div>
      <div
        v-else-if="item.type === 'placeholder' && shouldRenderRows"
        class="grid-view__group-by-rows-placeholder"
        :style="{
          top: item.y + 'px',
          height: item.height + 'px',
          width: sectionWidth + 'px',
        }"
      >
        <div
          v-for="(value, index) in placeholderPositions"
          :key="'placeholder-column-' + index"
          class="grid-view__placeholder-column"
          :style="{ left: value - 1 + 'px' }"
        ></div>
      </div>
      <button
        v-else-if="item.type === 'addRow' && shouldRenderAddRows"
        type="button"
        class="grid-view__row grid-view__group-by-rows-add"
        :style="{
          top: item.y + 'px',
          height: item.height + 'px',
          width: sectionWidth + 'px',
        }"
        @click="addRow($event, item.path)"
        @mouseover="setAddRowHover(item.path)"
        @mouseleave="setAddRowHover(null)"
      >
        <span
          class="grid-view__add-row"
          :class="{ hover: isAddRowHovered(item.path) }"
        >
          <i
            v-if="includeRowDetails"
            class="grid-view__add-row-icon iconoir-plus"
          ></i>
        </span>
      </button>
      <div
        v-else-if="item.type === 'groupSkeleton'"
        class="grid-view__group-by-banner grid-view__group-by-banner--skeleton"
        :style="{
          top: item.y + 'px',
          height: item.height + 'px',
          width: sectionWidth + 'px',
        }"
      >
        <div
          v-if="includeRowDetails"
          class="grid-view__group-by-banner-chevron-lane"
          :style="{
            width: gridViewRowDetailsWidth + 'px',
            paddingLeft: groupSkeletonIndent(item.depth) + 'px',
          }"
        >
          <span class="grid-view__group-by-banner-skeleton-chevron"></span>
        </div>
        <div class="grid-view__group-by-banner-skeleton-line"></div>
      </div>
    </template>
  </div>
</template>

<script>
import GridViewRow from '@baserow/modules/database/components/view/grid/GridViewRow'
import GridViewGroupByBanner from '@baserow/modules/database/components/view/grid/GridViewGroupByBanner'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  pathKey,
  groupBannerIndentPx,
} from '@baserow/modules/database/utils/gridGroupByRender'

export default {
  name: 'GridViewGroupByRows',
  components: { GridViewRow, GridViewGroupByBanner },
  mixins: [gridViewHelpers],
  props: {
    renderedFields: { type: Array, required: true },
    visibleFields: { type: Array, required: true },
    allVisibleFields: { type: Array, required: true },
    allFieldsInTable: { type: Array, required: true },
    decorationsByPlace: { type: Object, required: true },
    leftOffset: { type: Number, default: 0 },
    view: { type: Object, required: true },
    includeRowDetails: { type: Boolean, default: false },
    readOnly: { type: Boolean, required: true },
    canAddRow: { type: Boolean, default: false },
    workspaceId: { type: Number, required: true },
    focusEntriesByCell: {
      type: Map,
      default: () => new Map(),
    },
    focusEntriesByRow: {
      type: Map,
      default: () => new Map(),
    },
  },
  emits: [
    'update',
    'paste',
    'edit',
    'cell-mousedown-left',
    'cell-mouseover',
    'cell-mouseup-left',
    'cell-shift-click',
    'cell-selected',
    'selected',
    'unselected',
    'select',
    'unselect',
    'select-next',
    'add-row',
    'add-row-after',
    'edit-modal',
    'refresh-row',
    'row-dragging',
    'row-hover',
    'row-context',
    'editing-changed',
  ],
  computed: {
    groupByFields() {
      return this.activeGroupBys
        .map((groupBy) =>
          this.allFieldsInTable.find((field) => field.id === groupBy.field)
        )
        .filter(Boolean)
    },
    visibleItems() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getGroupByVisibleItems'
      ](this.groupByFields)
    },
    totalHeight() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getGroupByLayout'
      ].totalHeight
    },
    fieldWidths() {
      const fieldWidths = {}
      this.visibleFields.forEach((field) => {
        fieldWidths[field.id] = this.getFieldWidth(field)
      })
      return fieldWidths
    },
    sectionWidth() {
      let width = this.visibleFields.reduce(
        (value, field) => this.getFieldWidth(field) + value,
        0
      )
      if (this.includeRowDetails) {
        width += this.gridViewRowDetailsWidth
      }
      return width
    },
    placeholderPositions() {
      let last = this.includeRowDetails ? this.gridViewRowDetailsWidth : 0
      const positions = {}
      this.visibleFields.forEach((field) => {
        last += this.getFieldWidth(field)
        positions[field.id] = last
      })
      return positions
    },
    shouldRenderRows() {
      return this.includeRowDetails || this.visibleFields.length > 0
    },
    shouldRenderAddRows() {
      return this.canAddRow && this.shouldRenderRows
    },
    addRowHoverPathKey() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getGroupByAddRowHoverPathKey'
      ]
    },
  },
  methods: {
    rowClass(row) {
      return {
        'grid-view__group-by-rows-row--warning': this.isWarningRow(row),
        'grid-view__group-by-rows-row--selected': row._.selected,
        'grid-view__group-by-rows-row--presence': this.rowHasPresence(row),
      }
    },
    rowHasPresence(row) {
      if (this.focusEntriesByRow.has(row.id)) return true
      const prefix = `${row.id}:`
      for (const key of this.focusEntriesByCell.keys()) {
        if (key.startsWith(prefix)) return true
      }
      return false
    },
    addRow(event, path) {
      event.preventFieldCellUnselect = true
      this.$emit('add-row', { groupPath: path })
    },
    setAddRowHover(path) {
      this.$store.dispatch(
        this.storePrefix + 'view/grid/setGroupByAddRowHover',
        path === null ? null : pathKey(path, this.groupByFields)
      )
    },
    isAddRowHovered(path) {
      return (
        this.addRowHoverPathKey !== null &&
        this.addRowHoverPathKey === pathKey(path, this.groupByFields)
      )
    },
    groupSkeletonIndent(depth) {
      return groupBannerIndentPx(
        depth,
        this.groupByFields.length,
        this.gridViewRowDetailsWidth
      )
    },
    itemKey(item) {
      // Use pathKey (set-based for m2m) so the same group keeps a stable Vue key
      // regardless of the id order in its path.
      if (item.type === 'header') {
        return `header-${pathKey(item.path, this.groupByFields)}`
      }
      if (item.type === 'row') {
        return `row-${item.row._.persistentId}`
      }
      if (item.type === 'addRow') {
        return `add-${pathKey(item.path, this.groupByFields)}`
      }
      if (item.type === 'groupSkeleton') {
        return `skeleton-${item.y}`
      }
      return `placeholder-${item.globalRowOffset}`
    },
    isWarningRow(row) {
      return !row._.matchFilters || !row._.matchSortings || !row._.matchSearch
    },
    async toggleGroup(path) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/toggleGroupCollapse',
          {
            path,
            view: this.view,
            fields: this.allFieldsInTable,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async onAggregationChanged(fieldId) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/refreshGroupByAggregations',
          {
            view: this.view,
            fields: this.allFieldsInTable,
            fieldId,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>

<template>
  <div class="grid-view__group-by-rows" :style="{ height: totalHeight + 'px' }">
    <template v-for="item in visibleItems" :key="itemKey(item)">
      <GridViewGroupByBanner
        v-if="item.type === 'header'"
        :item="item"
        :group-by-fields="groupByFields"
        :include-row-details="includeRowDetails"
        :primary-field-width="primaryFieldWidth"
        :row-details-width="gridViewRowDetailsWidth"
        :workspace-id="workspaceId"
        :width="sectionWidth"
        @toggle="toggleGroup"
      />
      <div
        v-else-if="item.type === 'row' && shouldRenderRows"
        class="grid-view__group-by-rows-row"
        :class="{
          'grid-view__group-by-rows-row--warning': isWarningRow(item.row),
          'grid-view__group-by-rows-row--selected': item.row._.selected,
        }"
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
          :store-prefix="storePrefix"
          :row-identifier-type="view.row_identifier_type"
          :count="item.globalRowOffset + 1"
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
        :style="{ top: item.y + 'px', height: item.height + 'px' }"
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
        :style="{ top: item.y + 'px', height: item.height + 'px' }"
        @click="addRow($event, item.path)"
      >
        <span class="grid-view__add-row">
          <i
            v-if="includeRowDetails"
            class="grid-view__add-row-icon iconoir-plus"
          ></i>
        </span>
      </button>
    </template>
  </div>
</template>

<script>
import GridViewRow from '@baserow/modules/database/components/view/grid/GridViewRow'
import GridViewGroupByBanner from '@baserow/modules/database/components/view/grid/GridViewGroupByBanner'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import { notifyIf } from '@baserow/modules/core/utils/error'

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
    workspaceId: { type: Number, required: true },
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
    primaryFieldWidth() {
      const primaryField = this.visibleFields[0]
      return primaryField ? this.getFieldWidth(primaryField) : 0
    },
    shouldRenderRows() {
      return this.includeRowDetails || this.visibleFields.length > 0
    },
    shouldRenderAddRows() {
      return !this.readOnly && this.shouldRenderRows
    },
  },
  methods: {
    addRow(event, path) {
      event.preventFieldCellUnselect = true
      this.$emit('add-row', { groupPath: path })
    },
    itemKey(item) {
      if (item.type === 'header') {
        return `header-${JSON.stringify(item.path)}`
      }
      if (item.type === 'row') {
        return `row-${item.row._.persistentId}`
      }
      if (item.type === 'addRow') {
        return `add-${JSON.stringify(item.path)}`
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
  },
}
</script>

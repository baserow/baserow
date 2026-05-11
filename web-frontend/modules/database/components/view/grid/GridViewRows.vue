<template>
  <div
    class="grid-view__rows"
    :style="{
      transform: `translateY(${rowsTop}px) translateX(${leftOffset || 0}px)`,
      left: '0px',
    }"
  >
    <template
      v-for="(item, index) in visibleItems"
      :key="
        item.type === 'row'
          ? `row-${item.row._.persistentId}`
          : `header-${index}`
      "
    >
      <GridViewGroupHeader
        v-if="item.type === 'header'"
        :field="item.field"
        :value="item.groupValues[`field_${item.field.id}`]"
        :count="item.count"
        :depth="item.depth"
        :collapsed="item.collapsed"
        :left-offset="leftOffset || 0"
        :row-details-width="includeRowDetails ? gridViewRowDetailsWidth : 0"
        :width="sectionWidth"
        @toggle-collapse="$emit('toggle-collapse', item.groupValues)"
      />
      <div
        v-else-if="item.type === 'subtree-skeleton'"
        class="grid-view__subtree-skeleton"
        :style="{
          height: (item.height || 48) + 'px',
          width: sectionWidth + 'px',
        }"
      >
        <div
          v-if="item.loading"
          class="grid-view__subtree-skeleton-spinner loading-spinner"
        ></div>
      </div>
      <GridViewRow
        v-else
        :group-end="isGroupEnd(index)"
        :view="view"
        :workspace-id="workspaceId"
        :row="item.row"
        :rendered-fields="renderedFields"
        :visible-fields="visibleFields"
        :all-visible-fields="allVisibleFields"
        :all-fields-in-table="allFieldsInTable"
        :field-widths="fieldWidths"
        :include-row-details="includeRowDetails"
        :decorations-by-place="decorationsByPlace"
        :read-only="readOnly"
        :can-drag="
          canDrag && view.sortings.length === 0 && activeGroupBys.length === 0
        "
        :store-prefix="storePrefix"
        :row-identifier-type="view.row_identifier_type"
        :count="getRowCount(index)"
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
    </template>
  </div>
</template>

<script>
import GridViewRow from '@baserow/modules/database/components/view/grid/GridViewRow'
import GridViewGroupHeader from '@baserow/modules/database/components/view/grid/GridViewGroupHeader'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'

export default {
  name: 'GridViewRows',
  components: { GridViewGroupHeader, GridViewRow },
  mixins: [gridViewHelpers],
  props: {
    /**
     * The visible fields that are within the viewport. The other ones are not rendered
     * for performance reasons.
     */
    renderedFields: {
      type: Array,
      required: true,
    },
    /**
     * The fields that are chosen to be visible within the view.
     */
    visibleFields: {
      type: Array,
      required: true,
    },
    allVisibleFields: {
      type: Array,
      required: true,
    },
    /**
     * All the fields in the table, regardless of the visibility, or whether they
     * should be rendered.
     */
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    decorationsByPlace: {
      type: Object,
      required: true,
    },
    leftOffset: {
      type: Number,
      required: false,
      default: 0,
    },
    view: {
      type: Object,
      required: true,
    },
    includeRowDetails: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    workspaceId: {
      type: Number,
      required: true,
    },
    interleavedItems: {
      type: Array,
      required: true,
    },
    sectionWidth: {
      type: Number,
      required: true,
    },
    canDrag: {
      type: Boolean,
      default: false,
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
    'add-row-after',
    'edit-modal',
    'refresh-row',
    'row-dragging',
    'row-hover',
    'row-context',
    'toggle-collapse',
  ],
  computed: {
    fieldWidths() {
      const fieldWidths = {}
      this.visibleFields.forEach((field) => {
        fieldWidths[field.id] = this.getFieldWidth(field)
      })
      return fieldWidths
    },
    visibleItems() {
      return this.interleavedItems
    },
    rowsTop() {
      return this.$store.getters[this.storePrefix + 'view/grid/getRowsTop']
    },
    rowsStartIndex() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getRowsStartIndex'
      ]
    },
    rowsEndIndex() {
      return this.$store.getters[this.storePrefix + 'view/grid/getRowsEndIndex']
    },
    bufferStartIndex() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getBufferStartIndex'
      ]
    },
    activeGroupBys() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getActiveGroupBys'
      ]
    },
  },
  methods: {
    isGroupEnd(index) {
      const next = this.visibleItems[index + 1]
      return next === undefined || next.type === 'header'
    },
    getRowCount(index) {
      const rowsBefore = this.visibleItems
        .slice(0, index + 1)
        .filter((item) => item.type === 'row').length
      return this.bufferStartIndex + rowsBefore
    },
  },
}
</script>

<template>
  <div
    class="grid-view__rows"
    :style="{
      transform: `translateY(${rowsTop}px) translateX(${leftOffset || 0}px)`,
      left: (includeGroupBy ? activeGroupByWidth : 0) + 'px',
    }"
  >
    <GridViewRow
      v-for="(row, index) in rows"
      :key="`row-${row._.persistentId}`"
      :group-end="rowsAtEndOfGroups.has(row.id)"
      :view="view"
      :workspace-id="workspaceId"
      :row="row"
      :rendered-fields="renderedFields"
      :visible-fields="visibleFields"
      :all-fields-in-table="allFieldsInTable"
      :primary-field-is-sticky="primaryFieldIsSticky"
      :field-widths="fieldWidths"
      :include-row-details="includeRowDetails"
      :include-group-by="includeGroupBy"
      :decorations-by-place="decorationsByPlace"
      :read-only="readOnly"
      :can-drag="
        canDrag && view.sortings.length === 0 && activeGroupBys.length === 0
      "
      :store-prefix="storePrefix"
      :row-identifier-type="view.row_identifier_type"
      :count="index + rowsStartIndex + bufferStartIndex + 1"
      v-on="$listeners"
    />
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import GridViewRow from '@baserow/modules/database/components/view/grid/GridViewRow'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'

export default {
  name: 'GridViewRows',
  components: { GridViewRow },
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
    includeGroupBy: {
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
    primaryFieldIsSticky: {
      type: Boolean,
      required: false,
      default: () => true,
    },
    rowsAtEndOfGroups: {
      type: Set,
      required: true,
    },
    canDrag: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    fieldWidths() {
      const fieldWidths = {}
      this.visibleFields.forEach((field) => {
        fieldWidths[field.id] = this.getFieldWidth(field)
      })
      return fieldWidths
    },
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        rows: this.$options.propsData.storePrefix + 'view/grid/getRows',
        rowsTop: this.$options.propsData.storePrefix + 'view/grid/getRowsTop',
        rowsStartIndex:
          this.$options.propsData.storePrefix + 'view/grid/getRowsStartIndex',
        rowsEndIndex:
          this.$options.propsData.storePrefix + 'view/grid/getRowsEndIndex',
        bufferStartIndex:
          this.$options.propsData.storePrefix + 'view/grid/getBufferStartIndex',
        activeGroupBys:
          this.$options.propsData.storePrefix + 'view/grid/getActiveGroupBys',
      }),
    }
  },
}
</script>

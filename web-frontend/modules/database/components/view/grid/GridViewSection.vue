<template>
  <div
    ref="section"
    v-auto-scroll="{
      enabled: () => isMultiSelectHolding,
      orientation: 'horizontal',
      speed: 4,
      padding: 10,
      onScroll: (speed) => {
        $emit('scroll', { pixelY: 0, pixelX: speed })
        return false
      },
    }"
  >
    <div
      v-for="({ left }, index) in groupByDividers"
      :key="'group-by-divider-' + index"
      class="grid-view__group-by-divider"
      :style="{ left: left + 'px' }"
    ></div>
    <HorizontalResize
      v-for="({ groupBy, left }, index) in groupByDividers"
      :key="'group-by-width-' + index"
      class="grid-view__head-group-width-handle"
      :style="{ left: left + 'px' }"
      :width="groupBy.width"
      :min="GRID_VIEW_MIN_FIELD_WIDTH"
      @move="moveGroupWidth(groupBy, view, $event)"
      @update="updateGroupWidth(groupBy, view, database, readOnly, $event)"
    ></HorizontalResize>
    <div class="grid-view__inner" :style="{ 'min-width': width + 'px' }">
      <GridViewHead
        :database="database"
        :table="table"
        :view="view"
        :all-fields-in-table="allFieldsInTable"
        :visible-fields="visibleFields"
        :include-row-details="includeRowDetails"
        :include-add-field="includeAddField"
        :include-grid-view-identifier-dropdown="
          includeGridViewIdentifierDropdown
        "
        :include-group-by="includeGroupBy"
        :show-group-by-field-background="!useGroupByRows"
        :read-only="readOnly"
        :store-prefix="storePrefix"
        @field-created="$emit('field-created', $event)"
        @refresh="$emit('refresh', $event)"
        @dragging="handleFieldDragging($event)"
      ></GridViewHead>
      <div
        ref="body"
        v-auto-scroll="{
          enabled: () => isMultiSelectHolding,
          speed: 4,
          padding: 10,
          onScroll: (speed) => {
            $emit('scroll', { pixelY: speed, pixelX: 0 })
            return false
          },
        }"
        class="grid-view__body"
      >
        <div class="grid-view__body-inner">
          <GridViewPlaceholder
            v-if="!useGroupByRows"
            :visible-fields="visibleFields"
            :view="view"
            :include-row-details="includeRowDetails"
            :include-group-by="includeGroupBy"
            :store-prefix="storePrefix"
          ></GridViewPlaceholder>
          <GridViewGroupByRows
            v-if="useGroupByRows"
            ref="rows"
            :view="view"
            :rendered-fields="fieldsToRender"
            :visible-fields="visibleFields"
            :all-visible-fields="allVisibleFields"
            :all-fields-in-table="allFieldsInTable"
            :workspace-id="database.workspace.id"
            :decorations-by-place="decorationsByPlace"
            :left-offset="fieldsLeftOffset"
            :include-row-details="includeRowDetails"
            :read-only="readOnly"
            :can-add-row="canCreateRow"
            :focus-entries-by-cell="focusEntriesByCell"
            :focus-entries-by-row="focusEntriesByRow"
            :store-prefix="storePrefix"
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
            @add-row="$emit('add-row', $event)"
            @add-rows="$emit('add-rows', $event)"
            @add-row-after="$emit('add-row-after', $event)"
            @edit-modal="$emit('edit-modal', $event)"
            @refresh-row="$emit('refresh-row', $event)"
            @row-dragging="$emit('row-dragging', $event)"
            @row-hover="$emit('row-hover', $event)"
            @row-context="$emit('row-context', $event)"
          ></GridViewGroupByRows>
          <GridViewRows
            v-else-if="
              !useGroupByRows && (includeRowDetails || visibleFields.length > 0)
            "
            ref="rows"
            :view="view"
            :rendered-fields="fieldsToRender"
            :visible-fields="visibleFields"
            :all-visible-fields="allVisibleFields"
            :all-fields-in-table="allFieldsInTable"
            :workspace-id="database.workspace.id"
            :decorations-by-place="decorationsByPlace"
            :left-offset="fieldsLeftOffset"
            :include-row-details="includeRowDetails"
            :include-group-by="includeGroupBy"
            :read-only="readOnly"
            :can-drag="
              $hasPermission(
                'database.table.update_row',
                table,
                database.workspace.id
              )
            "
            :focus-entries-by-cell="focusEntriesByCell"
            :focus-entries-by-row="focusEntriesByRow"
            :store-prefix="storePrefix"
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
            @editing-changed="$emit('editing-changed', $event)"
            @edit-modal="$emit('edit-modal', $event)"
            @refresh-row="$emit('refresh-row', $event)"
            @row-dragging="$emit('row-dragging', $event)"
            @row-hover="$emit('row-hover', $event)"
            @row-context="$emit('row-context', $event)"
          ></GridViewRows>
          <GridViewRowAdd
            v-if="
              !useGroupByRows &&
              canCreateRow &&
              (includeRowDetails || visibleFields.length > 0)
            "
            :visible-fields="visibleFields"
            :include-row-details="includeRowDetails"
            :store-prefix="storePrefix"
            @add-row="$emit('add-row', $event)"
            @add-rows="$emit('add-rows', $event)"
          ></GridViewRowAdd>
          <div
            v-else-if="!useGroupByRows"
            class="grid-view__row-placeholder"
          ></div>
        </div>
      </div>
      <div class="grid-view__foot">
        <div v-if="includeRowDetails" class="grid-view__foot-info">
          {{ $t('gridView.rowCount', { count }) }}
        </div>
        <div
          v-for="field in visibleFields"
          :key="field.id"
          :style="{ width: getFieldWidth(field) + 'px' }"
        >
          <GridViewFieldFooter
            :database="database"
            :field="field"
            :view="view"
            :store-prefix="storePrefix"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import debounce from 'lodash/debounce'

import GridViewHead from '@baserow/modules/database/components/view/grid/GridViewHead'
import GridViewPlaceholder from '@baserow/modules/database/components/view/grid/GridViewPlaceholder'
import GridViewRows from '@baserow/modules/database/components/view/grid/GridViewRows'
import GridViewGroupByRows from '@baserow/modules/database/components/view/grid/GridViewGroupByRows'
import GridViewRowAdd from '@baserow/modules/database/components/view/grid/GridViewRowAdd'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import GridViewFieldFooter from '@baserow/modules/database/components/view/grid/GridViewFieldFooter'
import HorizontalResize from '@baserow/modules/core/components/HorizontalResize'

export default {
  name: 'GridViewSection',
  components: {
    HorizontalResize,
    GridViewHead,
    GridViewPlaceholder,
    GridViewRows,
    GridViewGroupByRows,
    GridViewRowAdd,
    GridViewFieldFooter,
  },
  mixins: [gridViewHelpers],
  props: {
    visibleFields: {
      type: Array,
      required: true,
    },
    allVisibleFields: {
      type: Array,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    decorationsByPlace: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
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
    includeAddField: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    includeGridViewIdentifierDropdown: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    canOrderFields: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    focusEntriesByCell: {
      type: Map,
      required: false,
      default: () => new Map(),
    },
    focusEntriesByRow: {
      type: Map,
      required: false,
      default: () => new Map(),
    },
    readOnly: {
      type: Boolean,
      required: true,
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
    'add-rows',
    'add-row-after',
    'edit-modal',
    'editing-changed',
    'refresh-row',
    'row-dragging',
    'row-hover',
    'row-context',
    'scroll',
    'field-created',
    'field-dragging',
    'refresh',
  ],
  data() {
    return {
      // Render the first 20 fields by default so that there's at least some data when
      // the page is server side rendered.
      fieldsToRender: this.visibleFields.slice(0, 20),
      // Indicates the offset
      fieldsLeftOffset: 0,
      resizeObserver: null,
      horizontalScrollEvent: null,
    }
  },
  computed: {
    /**
     * Calculates the total width of the whole section based on the fields and the
     * given options.
     */
    width() {
      let width = Object.values(this.visibleFields).reduce(
        (value, field) => this.getFieldWidth(field) + value,
        0
      )

      if (this.includeRowDetails) {
        width += this.gridViewRowDetailsWidth
      }
      if (this.includeGroupBy) {
        width += this.activeGroupByWidth
      }

      // The add button has a width of 100 and we reserve 100 at the right side.
      if (this.includeAddField) {
        width += 100 + 100
      }

      return width
    },
    groupByDividers() {
      if (!this.includeGroupBy) {
        return []
      }

      let last = 0
      const dividers = this.activeGroupBys
        .filter((groupBy, index) => index < this.activeGroupBys.length - 1)
        .map((groupBy) => {
          last += groupBy.width
          return { groupBy, left: last }
        })

      return dividers
    },
    useGroupByRows() {
      return this.activeGroupBys.length > 0
    },
    canCreateRow() {
      return (
        !this.readOnly &&
        (!this.table.data_sync || this.table.data_sync.two_way_sync) &&
        (this.$hasPermission(
          'database.table.create_row',
          this.table,
          this.database.workspace.id
        ) ||
          this.$hasPermission(
            'database.table.view.create_row',
            this.view,
            this.database.workspace.id
          ))
      )
    },
    isMultiSelectHolding() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/isMultiSelectHolding'
      ]
    },
    count() {
      return this.$store.getters[this.storePrefix + 'view/grid/getCount']
    },
  },
  watch: {
    fieldOptions: {
      deep: true,
      handler() {
        this.updateVisibleFieldsInRow()
      },
    },
    visibleFields: {
      deep: true,
      handler() {
        this.updateVisibleFieldsInRow()
      },
    },
  },
  mounted() {
    // When the component first loads, we need to check
    this.updateVisibleFieldsInRow()

    const updateDebounced = debounce(() => {
      this.updateVisibleFieldsInRow()
    }, 50)

    const sectionElement = this.$refs.section

    // When the viewport resizes, we need to check if there are fields that must be
    // rendered.
    this.resizeObserver = new ResizeObserver(() => {
      updateDebounced()
    })
    this.resizeObserver.observe(sectionElement)

    // When the user scrolls horizontally, we need to check if there fields/cells that
    // have moved into the viewport and must be rendered.
    const fireUpdateBuffer = {
      last: Date.now(),
      distance: 0,
    }
    this.horizontalScrollEvent = (event) => {
      // Call the update order debounce function to simulate a stop scrolling event.
      updateDebounced()

      const now = Date.now()
      const { scrollLeft } = event.target

      const distance = Math.abs(scrollLeft - fireUpdateBuffer.distance)
      const timeDelta = now - fireUpdateBuffer.last

      if (timeDelta > 100) {
        const velocity = distance / timeDelta

        fireUpdateBuffer.last = now
        fireUpdateBuffer.distance = scrollLeft

        if (velocity < 2.5) {
          updateDebounced.cancel()
          this.updateVisibleFieldsInRow()
        }
      }
    }
    sectionElement.addEventListener('scroll', this.horizontalScrollEvent)
  },
  beforeUnmount() {
    const sectionElement = this.$refs.section
    if (this.resizeObserver !== null) {
      this.resizeObserver.disconnect()
    }
    if (this.horizontalScrollEvent !== null) {
      sectionElement.removeEventListener('scroll', this.horizontalScrollEvent)
    }
  },
  methods: {
    handleFieldDragging(event) {
      if (!this.canOrderFields || event.field.primary) return
      this.$emit('field-dragging', event)
    },
    /**
     * For performance reasons we only want to render the cells are visible in the
     * viewport. This method makes sure that the right cells/fields are visible. It's
     * for example called when the user scrolls, when the window is resized or when a
     * field changes.
     */
    updateVisibleFieldsInRow() {
      if (!this.$el) return
      const width = this.$el.clientWidth
      const scrollLeft = this.$el.scrollLeft
      // The padding is added to the start and end of the viewport to make sure that
      // cells nearby will always be ready to be displayed.
      const padding = 200
      const viewportStart = scrollLeft - padding
      const viewportEnd = scrollLeft + width + padding
      let leftOffset = null
      let left = 0

      // Create an array containing the fields that are currently visible in the
      // viewport and must be rendered.
      const fieldsToRender = this.visibleFields.filter((field) => {
        const width = this.getFieldWidth(field)
        const right = left + width
        const visible = right >= viewportStart && left <= viewportEnd
        if (visible && leftOffset === null) {
          leftOffset = left
        }
        left = right
        return visible
      })

      if (
        JSON.stringify(this.fieldsToRender) !== JSON.stringify(fieldsToRender)
      ) {
        this.fieldsToRender = fieldsToRender
      }

      if (leftOffset !== this.fieldsLeftOffset) {
        this.fieldsLeftOffset = leftOffset
      }
    },
    getScrollElement() {
      return this.$refs.section
    },
  },
}
</script>

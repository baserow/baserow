<template>
  <div
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
        :include-field-width-handles="includeFieldWidthHandles"
        :include-row-details="includeRowDetails"
        :include-add-field="includeAddField"
        :include-grid-view-identifier-dropdown="
          includeGridViewIdentifierDropdown
        "
        :include-group-by="includeGroupBy"
        :read-only="readOnly"
        :store-prefix="storePrefix"
        @field-created="$emit('field-created', $event)"
        @refresh="$emit('refresh', $event)"
        @dragging="
          canOrderFields &&
            !$event.field.primary &&
            $refs.fieldDragging.start($event.field, $event.event)
        "
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
            :visible-fields="visibleFields"
            :view="view"
            :include-row-details="includeRowDetails"
            :include-group-by="includeGroupBy"
            :store-prefix="storePrefix"
          ></GridViewPlaceholder>
          <GridViewGroups
            v-if="includeGroupBy && activeGroupBys.length > 0"
            :all-fields-in-table="allFieldsInTable"
            :group-by-value-sets="groupByValueSets"
            :store-prefix="storePrefix"
          ></GridViewGroups>
          <GridViewRows
            v-if="includeRowDetails || visibleFields.length > 0"
            ref="rows"
            :view="view"
            :rendered-fields="fieldsToRender"
            :visible-fields="visibleFields"
            :all-fields-in-table="allFieldsInTable"
            :workspace-id="database.workspace.id"
            :decorations-by-place="decorationsByPlace"
            :left-offset="fieldsLeftOffset"
            :primary-field-is-sticky="primaryFieldIsSticky"
            :include-row-details="includeRowDetails"
            :include-group-by="includeGroupBy"
            :rows-at-end-of-groups="rowsAtEndOfGroups"
            :read-only="readOnly"
            :can-drag="
              $hasPermission(
                'database.table.update_row',
                table,
                database.workspace.id
              )
            "
            :store-prefix="storePrefix"
            v-on="$listeners"
          ></GridViewRows>
          <GridViewRowAdd
            v-if="
              !readOnly &&
              (!table.data_sync || table.data_sync.two_way_sync) &&
              (includeRowDetails || visibleFields.length > 0) &&
              ($hasPermission(
                'database.table.create_row',
                table,
                database.workspace.id
              ) ||
                $hasPermission(
                  'database.table.view.create_row',
                  view,
                  database.workspace.id
                ))
            "
            :visible-fields="visibleFields"
            :include-row-details="includeRowDetails"
            :store-prefix="storePrefix"
            v-on="$listeners"
          ></GridViewRowAdd>
          <div v-else class="grid-view__row-placeholder"></div>
        </div>
      </div>
      <div class="grid-view__foot">
        <div v-if="includeRowDetails" class="grid-view__foot-info">
          {{ $tc('gridView.rowCount', count, { count }) }}
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
    <GridViewFieldDragging
      ref="fieldDragging"
      :view="view"
      :fields="draggingFields"
      :offset="draggingOffset"
      :container-width="width"
      :read-only="
        readOnly ||
        !$hasPermission(
          'database.table.view.update_field_options',
          view,
          database.workspace.id
        )
      "
      :store-prefix="storePrefix"
      @scroll="$emit('scroll', $event)"
    ></GridViewFieldDragging>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import debounce from 'lodash/debounce'
import ResizeObserver from 'resize-observer-polyfill'

import GridViewHead from '@baserow/modules/database/components/view/grid/GridViewHead'
import GridViewPlaceholder from '@baserow/modules/database/components/view/grid/GridViewPlaceholder'
import GridViewGroups from '@baserow/modules/database/components/view/grid/GridViewGroups'
import GridViewRows from '@baserow/modules/database/components/view/grid/GridViewRows'
import GridViewRowAdd from '@baserow/modules/database/components/view/grid/GridViewRowAdd'
import GridViewFieldDragging from '@baserow/modules/database/components/view/grid/GridViewFieldDragging'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import GridViewFieldFooter from '@baserow/modules/database/components/view/grid/GridViewFieldFooter'
import HorizontalResize from '@baserow/modules/core/components/HorizontalResize'
import { fieldValuesAreEqualInObjects } from '@baserow/modules/database/utils/groupBy'

export default {
  name: 'GridViewSection',
  components: {
    HorizontalResize,
    GridViewHead,
    GridViewPlaceholder,
    GridViewGroups,
    GridViewRows,
    GridViewRowAdd,
    GridViewFieldDragging,
    GridViewFieldFooter,
  },
  mixins: [gridViewHelpers],
  props: {
    visibleFields: {
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
    includeFieldWidthHandles: {
      type: Boolean,
      required: false,
      default: () => true,
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
    primaryFieldIsSticky: {
      type: Boolean,
      required: false,
      default: () => true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      // Render the first 20 fields by default so that there's at least some data when
      // the page is server side rendered.
      fieldsToRender: this.visibleFields.slice(0, 20),
      // Indicates the offset
      fieldsLeftOffset: 0,
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

      // The add button has a width of 100 and we reserve 100 at the right side.
      if (this.includeAddField) {
        width += 100 + 100
      }

      return width
    },
    draggingFields() {
      return this.visibleFields.filter((f) => !f.primary)
    },
    draggingOffset() {
      let offset = this.visibleFields
        .filter((f) => f.primary)
        .reduce((sum, f) => sum + this.getFieldWidth(f), 0)

      if (this.includeRowDetails) {
        offset += this.gridViewRowDetailsWidth
      }

      return offset
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
    /**
     * Computes an object that can be used by the `GridViewGroups` and `GridViewRows`
     * components to correctly visualize the groups. Even though both components need
     * different data, we're computing it in the same function because having only one
     * loop is more efficient.
     *
     * groupBySets:
     *
     * Every entry in the array represents a group, and contains a list of spans, which
     * are essentially a row span of the rows in that group.
     *
     * [
     *   {
     *     "groupBy": object,
     *     "groupSpans": [
     *       {
     *         "rowSpan": 10,
     *         "value": any,
     *       },
     *       ...
     *     ]
     *   },
     *   ...
     * ]
     *
     * rowsAtEndOfGroups:
     *
     * Indicates whether the row is the start or end of the last group. This is needed
     * to add a visual divider
     *
     * [1, 2]
     *
     */
    groupBySetsAndRowsAtEndOfGroups() {
      const groupBys = this.activeGroupBys
      const metadata = this.groupByMetadata
      const rows = this.allRows
      const rowsAtEndOfGroups = new Set()

      const groupBySets = groupBys.map((groupBy, groupByIndex) => {
        const groupSpans = []
        let lastGroup = null

        rows.forEach((row, index) => {
          const previousRow = rows[index - 1]
          const nextRow = rows[index + 1]

          /**
           * Helper function that checks whether the value is the same for both rows in
           * this group, but also the previous ones. This is needed because we need to
           * start a new group if the previous value doesn't match.
           */
          const checkIfInSameGroup = (row1, row2) => {
            if (row1 === undefined || row2 === undefined) {
              return false
            }
            return groupBys.slice(0, groupByIndex + 1).every((groupBy) => {
              const groupByField = this.allFieldsInTable.find(
                (f) => f.id === groupBy.field
              )
              const groupByFieldType = this.$registry.get(
                'field',
                groupByField.type
              )
              return groupByFieldType.isEqual(
                groupByField,
                row1[`field_${groupBy.field}`],
                row2[`field_${groupBy.field}`]
              )
            })
          }

          if (!checkIfInSameGroup(previousRow, row)) {
            // The group by metadata is a dict where the key is equal to the group by,
            // and the value an array containing the count for each unique value
            // combination. Below we're looking through the entries to find the
            // matching count for the row values.
            const count =
              (metadata[`field_${groupBy.field}`] || []).find((entry) => {
                const groupByFields = groupBys
                  .slice(0, groupByIndex + 1)
                  .map((groupBy) => {
                    return this.allFieldsInTable.find(
                      (f) => f.id === groupBy.field
                    )
                  })
                return fieldValuesAreEqualInObjects(
                  groupByFields,
                  this.$registry,
                  entry,
                  row,
                  true
                )
              })?.count || -1

            // If the start of a group, then create a new span object in the last.
            lastGroup = {
              rowSpan: 1,
              value: row[`field_${groupBy.field}`],
              count,
            }
          } else {
            // If the value hasn't changed, it means that this row falls within the
            // already started group, to we have to increase the row span.
            lastGroup.rowSpan += 1
          }

          if (!checkIfInSameGroup(row, nextRow)) {
            // If the group ends, it must be added to the array.
            groupSpans.push(lastGroup)
            lastGroup = null

            // If we're at the last group, we want to store whether the row is last so
            // that we can visually show divider. This is only needed for the last group
            // because that's where the divider must match the one with the group.
            if (groupByIndex === groupBys.length - 1) {
              rowsAtEndOfGroups.add(row.id)
            }
          }
        })

        return { groupBy, groupSpans }
      })

      return { groupBySets, rowsAtEndOfGroups }
    },
    groupByValueSets() {
      return this.groupBySetsAndRowsAtEndOfGroups.groupBySets
    },
    rowsAtEndOfGroups() {
      return this.groupBySetsAndRowsAtEndOfGroups.rowsAtEndOfGroups
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
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        isMultiSelectHolding:
          this.$options.propsData.storePrefix +
          'view/grid/isMultiSelectHolding',
        count: this.$options.propsData.storePrefix + 'view/grid/getCount',
        allRows: this.$options.propsData.storePrefix + 'view/grid/getAllRows',
        groupByMetadata:
          this.$options.propsData.storePrefix + 'view/grid/getGroupByMetadata',
      }),
    }
  },
  mounted() {
    // When the component first loads, we need to check
    this.updateVisibleFieldsInRow()

    const updateDebounced = debounce(() => {
      this.updateVisibleFieldsInRow()
    }, 50)

    // When the viewport resizes, we need to check if there are fields that must be
    // rendered.
    this.$el.resizeObserver = new ResizeObserver(() => {
      updateDebounced()
    })
    this.$el.resizeObserver.observe(this.$el)

    // When the user scrolls horizontally, we need to check if there fields/cells that
    // have moved into the viewport and must be rendered.
    const fireUpdateBuffer = {
      last: Date.now(),
      distance: 0,
    }
    this.$el.horizontalScrollEvent = (event) => {
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
    this.$el.addEventListener('scroll', this.$el.horizontalScrollEvent)
  },
  beforeDestroy() {
    this.$el.resizeObserver.unobserve(this.$el)
    this.$el.removeEventListener('scroll', this.$el.horizontalScrollEvent)
  },
  methods: {
    /**
     * For performance reasons we only want to render the cells are visible in the
     * viewport. This method makes sure that the right cells/fields are visible. It's
     * for example called when the user scrolls, when the window is resized or when a
     * field changes.
     */
    updateVisibleFieldsInRow() {
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
  },
}
</script>

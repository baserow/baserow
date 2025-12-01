<template>
  <div
    class="timeline-grid"
    :style="{
      height: `${gridHeight}px`,
      width: `${gridWidth}px`,
    }"
  >
    <template v-for="({ position, item: col }, index) in columnsBuffer">
      <div
        v-show="col !== undefined"
        :key="`c-${index}`"
        :style="{
          position: 'absolute',
          left: `${position.left}px`,
          width: `${columnWidth}px`,
          height: `${gridHeight}px`,
        }"
        class="timeline-grid__column"
        :class="{ 'timeline-grid__column--alt': col?.altColor }"
      ></div>
    </template>

    <div
      v-if="offsetNow"
      :style="{
        position: 'absolute',
        left: `${offsetNow}px`,
        height: `${gridHeight}px`,
      }"
    >
      <div
        :style="{ height: `${minGridHeight}px` }"
        class="timeline-grid__now-cursor"
      ></div>
    </div>

    <template v-for="({ position, item: row }, index) in rowsBuffer">
      <div
        v-if="row"
        :key="`r-${index}`"
        class="timeline-grid__row-lane"
        :style="{
          height: `${rowHeight}px`,
          top: `${position.top}px`,
        }"
      >
        <div v-show="isValidRow(row)" class="timeline-grid__row">
          <!-- Pass strings instead of moment objects to prevent unnecessary re-renders -->
          <TimelineGridRow
            ::ref="`row-${row.id}`"
            :label="getRowLabel(row)"
            :start-date="getRowDateValue(row, startDateField)?.format()"
            :end-date="getRowDateValue(row, endDateField)?.format()"
            :timezone="timezone"
            :start-date-field-read-only="readOnly || startDateFieldReadOnly"
            :end-date-field-read-only="readOnly || endDateFieldReadOnly"
            :date-only-fields="dateOnlyFields"
            v-bind="getRowStyleProps(row)"
            @edit-row="$emit('edit-row', row)"
            @updating-row="$emit('updating-row', { row, value: $event })"
            @update-row="updateRow(row, $event)"
          />
        </div>

        <TimelineGridShowRowButton
          v-if="!isValidRow(row)"
          class="timeline-grid__show-row-button timeline-grid__show-row-button--goto-start"
          :label="getRowLabel(row)"
          :date="null"
          :timezone="timezone"
          icon="iconoir-expand"
          @mousedown="$emit('edit-row', row)"
        />
        <TimelineGridShowRowButton
          v-else-if="showGotoStartButton(row)"
          class="timeline-grid__show-row-button timeline-grid__show-row-button--goto-start"
          :label="getRowLabel(row)"
          :date="getRowDateValue(row, startDateField).format()"
          :timezone="timezone"
          @mousedown="scrollToStart(row, $event)"
        />
        <TimelineGridShowRowButton
          v-if="showGotoEndButton(row)"
          class="timeline-grid__show-row-button timeline-grid__show-row-button--goto-end"
          :label="getRowLabel(row)"
          :date="getRowDateValue(row, endDateField).format()"
          :timezone="timezone"
          :tooltip-position="`bottom-left`"
          icon="iconoir-nav-arrow-right"
          @mousedown="scrollToEnd(row, $event)"
        />
      </div>
    </template>
    <TimelineGridRowFieldRules
      :rows="rowsBuffer"
      :view="$parent.view"
      :fields="$parent.fields"
      :store-prefix="$parent.storePrefix"
    />
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import { getFieldTimezone } from '@baserow/modules/database/utils/date'
import TimelineGridRow from '@baserow_premium/components/views/timeline/TimelineGridRow'
import TimelineGridShowRowButton from '@baserow_premium/components/views/timeline/TimelineGridShowRowButton'
import TimelineGridRowFieldRules from '@baserow_premium/components/views/timeline/TimelineGridRowFieldRules.vue'

export default {
  name: 'TimelineGrid',
  components: {
    TimelineGridRowFieldRules,
    TimelineGridRow,
    TimelineGridShowRowButton,
  },
  provide: function () {
    const that = this
    return {
      getRowPosition: (rowItem) => {
        if (!rowItem.item) {
          return
        }
        const pos = that.getRowStyleProps(rowItem.item)
        const out = {
          left: pos.leftPadding + pos.left,
          top: rowItem.position.top,
          width: pos.width,
          height: that.rowHeight,
        }
        return out
      },
    }
  },
  props: {
    columnsBuffer: {
      type: Array,
      required: true,
    },
    columnWidth: {
      type: Number,
      required: true,
    },
    columnCount: {
      type: Number,
      required: true,
    },
    columnUnit: {
      type: String, // only 'day' is supported for now
      required: true,
    },
    rowsBuffer: {
      type: Array,
      required: true,
    },
    rowCount: {
      type: Number,
      required: true,
    },
    rowHeight: {
      type: Number,
      required: true,
    },
    minGridHeight: {
      type: Number,
      required: true,
    },
    firstAvailableDate: {
      type: Object, // a moment object
      required: true,
    },
    lastAvailableDate: {
      type: Object, // a moment object
      required: true,
    },
    startDateField: {
      type: Object,
      required: true,
    },
    endDateField: {
      type: Object,
      required: true,
    },
    visibleFields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    decorationsByPlace: {
      type: Object,
      required: true,
    },
    scrollLeft: {
      type: Number,
      default: 0,
    },
    step: {
      type: String, // the step unit of the timeline. I.e. 'hour' in a daily view
      required: true,
    },
  },
  computed: {
    gridHeight() {
      // Add 2 rows to the grid height to keep the last row above the add button.
      return Math.max((this.rowCount + 2) * this.rowHeight, this.minGridHeight)
    },
    gridWidth() {
      return this.columnCount * this.columnWidth
    },
    offsetNow() {
      return this.leftOffsetOf(moment().tz(this.timezone))
    },
    timezone() {
      const tz = this.startDateField
        ? getFieldTimezone(this.startDateField)
        : null
      return tz || 'UTC'
    },
    firstVisibleDate() {
      if (this.columnsBuffer.length === 0) {
        return null
      }
      return this.columnsBuffer[0].item?.date || null
    },
    lastVisibleDate() {
      const lastColumn = this.columnsBuffer.length - 1
      if (lastColumn < 0) {
        return null
      }
      return this.columnsBuffer[lastColumn].item?.date || null
    },
    startDateFieldReadOnly() {
      return this.isReadOnlyField(this.startDateField)
    },
    endDateFieldReadOnly() {
      return this.isReadOnlyField(this.endDateField)
    },
    // Decorations from the viewDecoration mixin
    firstCellDecorations() {
      return this.decorationsByPlace?.first_cell || []
    },
    wrapperDecorations() {
      return this.decorationsByPlace?.wrapper || []
    },
    dateOnlyFields() {
      return !this.startDateField?.date_include_time
    },
    // The width of the step in pixels
    stepPx() {
      const ratio =
        moment.duration(1, this.step) / moment.duration(1, this.columnUnit)
      return ratio * this.columnWidth
    },
  },
  methods: {
    /*
     * Returns true if the given field is read only or the user doesn't have the
     * permissions to update values.
     */
    isReadOnlyField(field) {
      const fieldType = this.$registry.get('field', field.type)
      return !fieldType.canWriteFieldValues(field)
    },
    /*
     * Returns the left offset of the given date in the timeline grid.
     */
    leftOffsetOf(date) {
      const diffInUnits = date.diff(
        this.firstAvailableDate,
        this.columnUnit,
        true
      )
      return diffInUnits * this.columnWidth
    },
    /*
     * Returns the date value of the given field in the given row.
     */
    getRowDateValue(row, field) {
      const value = row[`field_${field.id}`]
      if (!value) {
        return null
      }
      return moment(value).tz(this.timezone, true)
    },
    /*
     * Returns the style for the event of the given row. The style includes the left
     * offset and the width of the event based on the start and end date of the row.
     */
    getRowStyleProps(row) {
      let left = 0
      let width = 0
      const minWidth = this.columnWidth / 2
      const step = this.stepPx
      const leftPadding = 2
      const rightPadding = 3
      const backgroundColor = this.backgroundColorForRow(row)
      const leftBorderColor = this.leftBorderColorForRow(row)

      if (row && this.isValidRow(row)) {
        const startDate = this.getRowDateValue(row, this.startDateField)
        let endDate = this.getRowDateValue(row, this.endDateField)
        if (this.dateOnlyFields) {
          // include the whole day for date only fields
          endDate = endDate.clone().add(1, 'day')
        }
        left = this.leftOffsetOf(startDate)
        width = this.leftOffsetOf(endDate) - left
      }

      return {
        scrollLeft: this.scrollLeft,
        left,
        width,
        minWidth,
        step,
        leftPadding,
        rightPadding,
        backgroundColor,
        leftBorderColor,
      }
    },
    /*
     * Returns the label of the given row. The label is a human readable string that
     * represents the row based on the visible fields.
     */
    getRowLabel(row) {
      return this.visibleFields
        .map((f) => {
          const fieldType = this.$registry.get('field', f.type)
          const cellValue = row[`field_${f.id}`]
          return fieldType.toHumanReadableString(f, cellValue)
        })
        .join(' - ')
    },
    /*
     * Returns true if the given row is valid. A row is valid if it has a start and end
     * date, the end date is after the start date, and the row is within the available
     * date range.
     */
    isValidRow(row) {
      if (this.firstVisibleDate === null || this.lastVisibleDate === null) {
        return false
      }
      const startDate = this.getRowDateValue(row, this.startDateField)
      const endDate = this.getRowDateValue(row, this.endDateField)
      return (
        startDate &&
        endDate &&
        endDate.isSameOrAfter(startDate) &&
        startDate.isSameOrAfter(this.firstAvailableDate) &&
        endDate.isSameOrBefore(this.lastAvailableDate)
      )
    },
    /*
     * Returns true if the goto start date is not visible in the current view so that
     * the user can scroll to it.
     */
    showGotoStartButton(row) {
      if (!this.isValidRow(row)) {
        return false
      }
      const startDate = this.getRowDateValue(row, this.startDateField)
      return startDate
        .clone()
        .subtract(1, this.columnUnit)
        .isBefore(this.firstVisibleDate)
    },
    /*
     * Returns true if the goto end date is not visible in the current view so that
     * the user can scroll to it.
     */
    showGotoEndButton(row) {
      if (!this.isValidRow(row)) {
        return false
      }
      const endDate = this.getRowDateValue(row, this.endDateField)
      return endDate.isAfter(
        this.lastVisibleDate.clone().add(1, this.columnUnit)
      )
    },
    /*
     * Calculate the date to scroll to when the user clicks on the goto start button.
     * If the end date is before the first visible date and the path is shorter, the
     * end date is chosen. Otherwise the start date is chosen.
     */
    scrollToStart(row) {
      const startDate = this.getRowDateValue(row, this.startDateField)
      const endDate = this.getRowDateValue(row, this.endDateField)
      const pad = 2
      const visibleCols = this.lastVisibleDate.diff(
        this.firstVisibleDate,
        this.columnUnit
      )
      const toStart =
        this.firstVisibleDate.diff(startDate, this.columnUnit) + pad
      const toEnd = this.lastVisibleDate.diff(endDate, this.columnUnit) - pad
      let date
      if (toStart <= toEnd || endDate.isAfter(this.firstVisibleDate)) {
        date = startDate.clone().subtract(pad, this.columnUnit)
      } else {
        date = endDate.clone().subtract(visibleCols - pad, this.columnUnit)
      }
      this.$emit('scroll-to-date', date)
    },
    /*
     * Calculate the date to scroll to when the user clicks on the goto end button.
     * If the start date is after the last visible date and the path is shorter, the
     * start date is chosen. Otherwise the end date is chosen.
     */
    scrollToEnd(row) {
      const startDate = this.getRowDateValue(row, this.startDateField)
      const endDate = this.getRowDateValue(row, this.endDateField)
      const pad = 2
      const visibleCols = this.lastVisibleDate.diff(
        this.firstVisibleDate,
        this.columnUnit
      )
      const toStart =
        this.firstVisibleDate.diff(startDate, this.columnUnit) + pad
      const toEnd = this.lastVisibleDate.diff(endDate, this.columnUnit) - pad
      let date
      if (toStart <= toEnd || startDate.isBefore(this.lastVisibleDate)) {
        date = endDate.clone().subtract(visibleCols - pad, this.columnUnit)
      } else {
        date = startDate.clone().subtract(pad, this.columnUnit)
      }
      this.$emit('scroll-to-date', date)
    },
    /*
     * Updates the start and end date of the given row based on the given offsets.
     * This method is called when a row is resized or moved.
     */
    updateRow(row, { startOffset, endOffset }) {
      const startField = this.startDateField
      const newStartDate = this.getRowDateValue(row, startField).clone()

      if (startOffset !== 0) {
        const numberOfUnits = Math.round(startOffset / this.stepPx)
        newStartDate.add(numberOfUnits, this.step)
      }
      const start = this.$registry
        .get('field', startField.type)
        .formatValue(startField, newStartDate)

      const endField = this.endDateField
      const newEndDate = this.getRowDateValue(row, endField).clone()
      if (endOffset !== 0) {
        const numberOfUnits = Math.round(endOffset / this.stepPx)
        newEndDate.add(numberOfUnits, this.step)
      }
      const end = this.$registry
        .get('field', endField.type)
        .formatValue(endField, newEndDate)

      this.$emit('update-row', { row, start, end })
    },
    /*
     * Returns the background color for the given row.
     */
    backgroundColorForRow(row) {
      const colors = this.wrapperDecorations.map(
        (comp) => comp.propsFn(row).value
      )
      return colors.length > 0 ? colors[0] : null
    },
    /*
     * Returns the left border decorations for the given row.
     */
    leftBorderColorForRow(row) {
      const colors = this.firstCellDecorations.map(
        (comp) => comp.propsFn(row).value
      )
      return colors.length > 0 ? colors[0] : null
    },
  },
}
</script>

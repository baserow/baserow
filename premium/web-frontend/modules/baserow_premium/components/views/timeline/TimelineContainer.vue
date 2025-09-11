<template>
  <div class="timeline-container">
    <div v-if="firstVisibleDate" class="timeline-container__header">
      <ViewDateIndicator :date="firstVisibleDate" :format="headerFormat" />
      <div class="timeline-container__header-right">
        <ViewDateSelector
          :selected-date="firstVisibleDate"
          :unit="timescale"
          @date-selected="scrollDateIntoView"
        />
        <Button
          type="secondary"
          class="timeline-container__header-timescale"
          size="large"
          :icon="`iconoir-nav-arrow-${
            $refs.timescaleContext?.isOpen() ? 'up' : 'down'
          }`"
          @click="toggleTimescaleContext"
        >
          {{ $t(`timelineTimescaleContext.${view.timescale}`) }}
        </Button>
        <TimelineTimescaleContext
          ref="timescaleContext"
          :timescale="view.timescale"
          :start-date-field="startDateField"
          @select="updateTimescale"
        />
      </div>
    </div>
    <div ref="gridHeader" class="timeline-container__grid-header">
      <TimelineGridHeader
        v-if="gridReady"
        :columns-buffer="columnsBuffer"
        :column-count="columnCount"
        :column-width="columnWidth"
        :date-format="columnHeaderFormat"
      />
    </div>
    <div
      ref="gridBody"
      v-auto-scroll="{
        enabled: () =>
          enableAutoScroll && $refs.gridBody.scrollLeft < scrollLeftLimit,
        orientation: 'horizontal',
        speed: 5,
        padding: 20,
      }"
      class="timeline-container__grid-body"
    >
      <TimelineGrid
        v-if="gridReady"
        :columns-buffer="columnsBuffer"
        :column-width="columnWidth"
        :column-count="columnCount"
        :column-unit="unit"
        :rows-buffer="rowsBuffer"
        :row-count="rowCount"
        :row-height="rowHeight"
        :min-grid-height="gridHeight"
        :start-date-field="startDateField"
        :end-date-field="endDateField"
        :visible-fields="visibleFields"
        :first-available-date="firstAvailableDate"
        :last-available-date="lastAvailableDate"
        :step="step"
        :read-only="
          readOnly ||
          (!$hasPermission(
            'database.table.update_row',
            table,
            database.workspace.id
          ) &&
            !$hasPermission(
              'database.table.view.update_row',
              view,
              database.workspace.id
            ))
        "
        :decorations-by-place="decorationsByPlace"
        :scroll-left="prevScrollLeft"
        @scroll-to-date="scrollDateIntoView"
        @edit-row="openRowEditModal($event)"
        @updating-row="enableAutoScroll = $event.value"
        @update-row="updateRowDates($event)"
      />
    </div>
    <ButtonFloating
      v-if="
        !readOnly &&
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
      icon="iconoir-plus"
      position="fixed"
      @click="$refs.rowCreateModal.show()"
    >
    </ButtonFloating>
    <RowEditModal
      ref="rowEditModal"
      enable-navigation
      :database="database"
      :table="table"
      :view="view"
      :all-fields-in-table="fields"
      :primary-is-sortable="true"
      :visible-fields="visibleFields"
      :hidden-fields="hiddenFields"
      :rows="rows"
      :read-only="
        readOnly ||
        (!$hasPermission(
          'database.table.update_row',
          table,
          database.workspace.id
        ) &&
          !$hasPermission(
            'database.table.view.update_row',
            view,
            database.workspace.id
          ))
      "
      :show-hidden-fields="showHiddenFieldsInRowModal"
      @hidden="$emit('selected-row', undefined)"
      @toggle-hidden-fields-visibility="
        showHiddenFieldsInRowModal = !showHiddenFieldsInRowModal
      "
      @update="updateValue"
      @order-fields="orderFields"
      @toggle-field-visibility="toggleFieldVisibility"
      @field-updated="$emit('refresh', $event)"
      @field-deleted="$emit('refresh')"
      @field-created="showFieldCreated"
      @field-created-callback-done="afterFieldCreatedUpdateFieldOptions"
      @navigate-previous="$emit('navigate-previous', $event, activeSearchTerm)"
      @navigate-next="$emit('navigate-next', $event, activeSearchTerm)"
      @refresh-row="refreshRow"
    >
    </RowEditModal>
    <RowCreateModal
      v-if="
        !readOnly &&
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
      ref="rowCreateModal"
      :database="database"
      :table="table"
      :view="view"
      :primary-is-sortable="true"
      :visible-fields="visibleFields"
      :hidden-fields="hiddenFields"
      :show-hidden-fields="showHiddenFieldsInRowModal"
      :all-fields-in-table="fields"
      @toggle-hidden-fields-visibility="
        showHiddenFieldsInRowModal = !showHiddenFieldsInRowModal
      "
      @created="createRow"
      @order-fields="orderFields"
      @toggle-field-visibility="toggleFieldVisibility"
      @field-updated="$emit('refresh', $event)"
      @field-deleted="$emit('refresh')"
    ></RowCreateModal>
  </div>
</template>
<script>
import { mapGetters } from 'vuex'
import debounce from 'lodash/debounce'
import moment from '@baserow/modules/core/moment'
import {
  recycleSlots,
  orderSlots,
} from '@baserow/modules/database/utils/virtualScrolling'
import {
  sortFieldsByOrderAndIdFunction,
  filterVisibleFieldsFunction,
  filterHiddenFieldsFunction,
} from '@baserow/modules/database/utils/view'
import ViewDateIndicator from '@baserow_premium/components/views/ViewDateIndicator'
import ViewDateSelector from '@baserow_premium/components/views/ViewDateSelector'
import TimelineGridHeader from '@baserow_premium/components/views/timeline/TimelineGridHeader'
import TimelineGrid from '@baserow_premium/components/views/timeline/TimelineGrid'
import TimelineTimescaleContext from '@baserow_premium/components/views/timeline/TimelineTimescaleContext'
import viewHelpers from '@baserow/modules/database/mixins/viewHelpers'
import timelineViewHelpers from '@baserow_premium/mixins/timelineViewHelpers'
import RowCreateModal from '@baserow/modules/database/components/row/RowCreateModal'
import RowEditModal from '@baserow/modules/database/components/row/RowEditModal'
import { populateRow } from '@baserow/modules/database/store/view/grid'
import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ResizeObserver from 'resize-observer-polyfill'
import viewDecoration from '@baserow/modules/database/mixins/viewDecoration'

const timescales = {
  day: () => ({
    headerFormat: 'll',
    columnHeaderFormat: 'HH',
    unit: 'hour',
    timescale: 'day',
    visibleColumnCount: 24,
    firstDate: (timezone) =>
      moment().tz(timezone).subtract(4, 'year').startOf('year'),
    lastDate: (timezone) => moment().tz(timezone).add(10, 'year').endOf('year'),
    step: () => 'hour',
    altColor: (date) => date.hour() % 12 === 0,
  }),
  week: () => ({
    headerFormat: 'MMMM YYYY',
    columnHeaderFormat: 'ddd D',
    unit: 'day',
    timescale: 'week',
    visibleColumnCount: 7,
    firstDate: (timezone) =>
      moment().tz(timezone).subtract(30, 'year').startOf('week'),
    lastDate: (timezone) => moment().tz(timezone).add(70, 'year').endOf('week'),
    altColor: (date) => date.isoWeekday() > 5,
    step: () => 'day',
  }),
  month: () => ({
    headerFormat: 'MMMM YYYY',
    columnHeaderFormat: 'D',
    unit: 'day',
    timescale: 'month',
    visibleColumnCount: 31,
    firstDate: (timezone) =>
      moment().tz(timezone).subtract(100, 'years').startOf('year'),
    lastDate: (timezone) =>
      moment().tz(timezone).add(500, 'years').endOf('year'),
    altColor: (date) => date.isoWeekday() > 5,
    step: () => 'day',
  }),
  year: () => ({
    headerFormat: 'YYYY',
    columnHeaderFormat: 'MMM',
    unit: 'month',
    timescale: 'year',
    visibleColumnCount: 12,
    firstDate: (timezone) =>
      moment().tz(timezone).subtract(130, 'years').startOf('year'),
    lastDate: (timezone) =>
      moment().tz(timezone).add(1500, 'years').endOf('year'),
    altColor: (date) => date.month() % 3 === 0,
    step: () => 'day',
  }),
}

export default {
  name: 'TimelineContainer',
  components: {
    RowCreateModal,
    RowEditModal,
    TimelineGridHeader,
    TimelineGrid,
    TimelineTimescaleContext,
    ViewDateIndicator,
    ViewDateSelector,
  },
  mixins: [viewHelpers, timelineViewHelpers, viewDecoration],
  props: {
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      // columns
      minColumnWidth: 32,
      columnWidth: 0,
      columnsBuffer: [],
      prevScrollLeft: 0,
      gridWidth: 0,
      columnHeaderFormat: null,
      // rows
      rowHeight: 33,
      rowsBuffer: [],
      prevScrollTop: 0,
      gridHeight: 0,
      // timescale settings
      headerFormat: '',
      unit: null,
      timescale: null,
      step: null,
      visibleColumnCount: null,
      firstAvailableDate: null,
      lastAvailableDate: null,
      //
      showHiddenFieldsInRowModal: false,
      enableAutoScroll: false,
      refreshingRow: false,
    }
  },
  computed: {
    columnCount() {
      return this.lastAvailableDate.diff(this.firstAvailableDate, this.unit) + 1
    },
    rows() {
      return this.$store.getters[this.storePrefix + 'view/timeline/getRows']
    },
    rowCount() {
      return this.rows.length
    },
    containerHeight() {
      return this.rowsCount * this.rowHeight
    },
    scrollAreaElement() {
      return this.$refs.gridBody
    },
    gridReady() {
      return this.columnWidth > 0
    },
    activeSearchTerm() {
      return this.$store.getters[
        `${this.storePrefix}view/timeline/getActiveSearchTerm`
      ]
    },
    fieldOptions() {
      return this.$store.getters[
        `${this.storePrefix}view/timeline/getAllFieldOptions`
      ]
    },
    visibleFields() {
      const fieldOptions = this.fieldOptions
      return this.fields
        .filter(filterVisibleFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
    },
    hiddenFields() {
      const fieldOptions = this.fieldOptions
      return this.fields
        .filter(filterHiddenFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
    },
    ...mapGetters({
      row: 'rowModalNavigation/getRow',
    }),
    firstVisibleDate() {
      if (this.columnsBuffer.length === 0) {
        return null
      }
      // The first fully visible column date
      return this.columnsBuffer[1].item?.date
    },
    scrollLeftLimit() {
      return (this.columnCount - this.visibleColumnCount) * this.columnWidth
    },
  },
  watch: {
    rows() {
      this.$nextTick(() => {
        const { startIndex, endIndex } = this.getVisibleRowsRange()
        this.updateRowsBuffer(startIndex, endIndex)
      })
    },
    row: {
      deep: true,
      handler(row, oldRow) {
        if (this.$refs.rowEditModal) {
          if (
            (oldRow === null && row !== null) ||
            (oldRow && row && oldRow.id !== row.id)
          ) {
            this.populateAndEditRow(row)
          } else if (oldRow !== null && row === null) {
            // Pass emit=false as argument into the hide function because that will
            // prevent emitting another `hidden` event of the `RowEditModal` which can
            // result in the route changing twice.
            this.$refs.rowEditModal.hide(false)
          }
        }
      },
    },
    'view.timescale'() {
      // Update the timescale as soon as it changes in the store.
      let currDate = this.firstVisibleDate
        .clone()
        .add(Math.floor(this.visibleColumnCount / 2), this.unit)

      this.setupGrid()

      if (currDate.isBefore(this.firstAvailableDate)) {
        currDate = this.firstAvailableDate.clone()
      } else if (currDate.isAfter(this.lastAvailableDate)) {
        currDate = this.lastAvailableDate
          .clone()
          .subtract(this.visibleColumnCount, this.unit)
      }

      this.$nextTick(() => {
        this.updateVisibleColumns()
        this.scrollDateIntoView(currDate, 'instant')
      })
    },
  },
  mounted() {
    this.initGrid()
    this.$nextTick(() => {
      // show today in the selected timescale
      const startOfTimescale = moment.tz(this.timezone).startOf(this.timescale)
      this.scrollDateIntoView(startOfTimescale, 'instant')
    })

    // Setup the scroll event listener to update the grid when the user scrolls

    const fetchAndUpdateVisibleRowsDebounced = debounce(async () => {
      await this.fetchAndUpdateVisibleRows()
    }, 80) // TODO: Use scroll speed to fetch more rows smartly (i.e. gallery view)
    const onScroll = () => {
      const el = this.scrollAreaElement

      if (Math.abs(el.scrollTop - this.prevScrollTop) > 1) {
        this.prevScrollTop = el.scrollTop
        fetchAndUpdateVisibleRowsDebounced()
      }

      const lastLeftPos = this.scrollLeftLimit
      if (el.scrollLeft > lastLeftPos) {
        el.scrollLeft = lastLeftPos
      }
      this.$refs.gridHeader.scrollLeft = el.scrollLeft

      const hasMoveLeft = Math.abs(el.scrollLeft - this.prevScrollLeft) > 1
      if (hasMoveLeft) {
        this.prevScrollLeft = el.scrollLeft
        this.updateVisibleColumns()
      }
    }

    const el = this.scrollAreaElement
    el.addEventListener('scroll', onScroll)
    this.$once('hook:beforeDestroy', () => {
      el.removeEventListener('scroll', onScroll)
    })

    // Setup the resize observer to update the grid when the size of the container changes.
    const setupGridDebounced = debounce(() => {
      this.onResizeUpdateGrid()
    }, 100)
    const resizeObserver = new ResizeObserver(() => {
      setupGridDebounced()
    })
    resizeObserver.observe(this.$el)
    this.$once('hook:beforeDestroy', () => {
      resizeObserver.disconnect()
    })

    // Open the row edit modal if the row is set.
    if (this.row !== null) {
      this.populateAndEditRow(this.row)
    }
  },
  methods: {
    /*
     * Initializes the grid by setting the timescale, columns, and rows.
     */
    initGrid() {
      this.setupGrid()
      this.fetchAndUpdateVisibleRows()
    },
    setupGrid() {
      this.initTimescale()
      this.updateGridDimensions()
      this.updateVisibleColumns()
    },
    /*
     * Initializes the timescale settings for the timeline view. These settings
     * determine the unit of time for the columns, the timescale, the number of
     * visible columns, and the format of the column headers.
     */
    initTimescale() {
      const timescale = this.view.timescale || 'month'
      const settings = timescales[timescale]()
      this.unit = settings.unit
      this.timescale = settings.timescale
      this.visibleColumnCount = settings.visibleColumnCount
      this.headerFormat = settings.headerFormat
      this.columnHeaderFormat = settings.columnHeaderFormat
      this.firstAvailableDate = settings.firstDate(this.timezone)
      this.lastAvailableDate = settings.lastDate(this.timezone)
      this.step = settings.step(this.startDateField)
      this.altColor = settings.altColor
    },
    /*
     * Returns the difference between two dates in the specified unit.
     */
    dateDiff(startDate, endDate, unit = this.unit, round = false) {
      return endDate.diff(startDate, unit, !round)
    },

    // Columns

    /*
     * Updates the grid based on the current scroll position.
     * If the column width has changed, we update it and recalculate the scroll offset
     * for today.
     */
    updateGridDimensions() {
      const el = this.scrollAreaElement
      this.gridWidth = el.clientWidth
      this.gridHeight = el.clientHeight
      this.columnWidth = Math.max(
        this.gridWidth / this.visibleColumnCount,
        this.minColumnWidth
      )
    },
    /*
     * Given the current horizontal scroll position, returns the range of visible columns.
     * This is used to determine which columns to render in the grid when the user scrolls
     * horizontally.
     */
    getVisibleColumnsRange() {
      const el = this.scrollAreaElement
      const startIndex = Math.floor(el.scrollLeft / this.columnWidth)
      const endIndex = startIndex + this.visibleColumnCount + 1
      return { startIndex, endIndex }
    },
    createColumn(index) {
      const date = moment(this.firstAvailableDate).add(index, this.unit)
      return {
        id: date.format(),
        date,
        altColor: this.altColor(date),
      }
    },
    /**
     * Updates the grid columns when the container is resized. It also scrolls the grid
     * to the same position as before the resize.
     */
    onResizeUpdateGrid() {
      const el = this.scrollAreaElement
      const prevPos = el.scrollLeft / el.scrollWidth

      this.updateGridDimensions()
      this.fetchAndUpdateVisibleRows()

      this.$nextTick(() => {
        // Use the proportion of the previous scroll position to calculate the new scroll
        // because the date can be rounded to the nearest unit.
        this.scrollLeft(prevPos * el.scrollWidth, 'instant')
      })
    },
    /**
     * Updates the grid columns when the user scrolls horizontally. Updates the
     * columnsBuffer to show the right columns and updates the firstVisibleDate to
     * follow the scroll.
     */
    updateVisibleColumns() {
      const { startIndex, endIndex } = this.getVisibleColumnsRange()
      const length = endIndex - startIndex
      const visibleColumns = Array.from({ length }, (_, i) =>
        this.createColumn(startIndex + i)
      )
      const getPosition = (col, pos) => ({
        left: (startIndex + pos) * this.columnWidth,
      })
      recycleSlots(this.columnsBuffer, visibleColumns, getPosition)
      orderSlots(this.columnsBuffer, visibleColumns)
    },
    /**
     * Scrolls the grid horizontally to the specified offset.
     */
    scrollLeft(left, behavior = 'instant') {
      this.scrollAreaElement.scroll({ left, behavior })
    },
    /**
     * Scrolls the grid horizontally to the specified date.
     */
    scrollDateIntoView(date, behaviour = 'smooth') {
      if (date.isBefore(this.firstAvailableDate)) {
        this.firstAvailableDate = date.clone().startOf(this.timescale)
      } else if (date.isAfter(this.lastAvailableDate)) {
        this.lastAvailableDate = date.clone().endOf(this.timescale)
      }
      const firstDate = this.firstAvailableDate
      const columnIndex = this.dateDiff(firstDate, date)
      this.scrollLeft(columnIndex * this.columnWidth, behaviour)
    },

    // Rows

    /**
     * Fetches the missing rows in the given range from the store.
     */
    async fetchMissingRows(startIndex, endIndex) {
      await this.$store.dispatch(
        this.storePrefix + 'view/timeline/fetchMissingRowsInNewRange',
        { startIndex, endIndex }
      )
    },
    /**
     * Returns the range of visible rows based on the current vertical scroll position.
     */
    getVisibleRowsRange() {
      const el = this.scrollAreaElement
      const elHeight = el.clientHeight
      const minRowsToRender = Math.ceil(elHeight / this.rowHeight) + 1
      let startIndex = Math.floor(el.scrollTop / this.rowHeight)
      let endIndex = startIndex + minRowsToRender
      if (endIndex > this.rowsCount) {
        endIndex = this.rowsCount
        startIndex = Math.max(0, endIndex - minRowsToRender)
      }
      return { startIndex, endIndex }
    },
    /**
     * Updates the rowsBuffer with the specified range of rows.
     */
    updateRowsBuffer(startIndex, endIndex) {
      const visibleRows = this.rows.slice(startIndex, endIndex)

      const getPosition = (row, pos) => ({
        top: (startIndex + pos) * this.rowHeight,
      })
      const rowsToRender = endIndex - startIndex
      recycleSlots(this.rowsBuffer, visibleRows, getPosition, rowsToRender)
      orderSlots(this.rowsBuffer, visibleRows)
    },
    async fetchAndUpdateVisibleRows() {
      const { startIndex, endIndex } = this.getVisibleRowsRange()
      await this.fetchMissingRows(startIndex, endIndex)
      this.updateRowsBuffer(startIndex, endIndex)
    },

    //

    /**
     * Creates a new row in the store and calls the callback when done.
     */
    async createRow({ row, callback }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/timeline/createNewRow',
          {
            view: this.view,
            table: this.table,
            fields: this.fields,
            values: row,
          }
        )
        callback()
      } catch (error) {
        callback(error)
      }
    },
    /**
     * Updates the value of a field in the store.
     */
    async updateValue({ field, row, value, oldValue }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/timeline/updateRowValue',
          {
            table: this.table,
            view: this.view,
            fields: this.fields,
            row,
            field,
            value,
            oldValue,
          }
        )
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
    /**
     * Update date fields in the store. This method is called when a row
     * is dragged and dropped to a new date range or when the user manually
     * changes the start or end date of a row with the resize handle.
     */
    async updateRowDates({ row, start, end }) {
      const values = {}
      const oldValues = {}

      if (start) {
        values[this.startDateField.id] = start
        oldValues[this.startDateField.id] =
          row[`field_${this.startDateField.id}`]
      }
      if (end) {
        values[this.endDateField.id] = end
        oldValues[this.endDateField.id] = row[`field_${this.endDateField.id}`]
      }

      if (!Object.keys(values).length) {
        return
      }

      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/timeline/updateRowValues',
          {
            table: this.table,
            view: this.view,
            fields: this.fields,
            row,
            values,
            oldValues,
          }
        )
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
    /**
     * Calls action in the store to refresh row directly from the backend - f. ex.
     * when editing row from a different table, when editing is complete, we need
     * to refresh the 'main' row that's 'under' the RowEdit modal.
     */
    refreshRow(row) {
      if (this.refreshingRow) {
        return
      }
      this.refreshingRow = true
      this.$nextTick(async () => {
        try {
          await this.$store.dispatch(
            this.storePrefix + 'view/timeline/refreshRowFromBackend',
            { table: this.table, row }
          )
        } catch (error) {
          notifyIf(error, 'row')
        } finally {
          this.refreshingRow = false
        }
      })
    },
    /**
     * Calls the fieldCreated callback and shows the hidden fields section
     * because new fields are hidden by default.
     */
    showFieldCreated({ fetchNeeded, ...context }) {
      this.fieldCreated({ fetchNeeded, ...context })
      this.showHiddenFieldsInRowModal = true
    },
    /**
     * Opens the row edit modal for the given row.
     */
    openRowEditModal(row) {
      this.$refs.rowEditModal.show(row.id)
      this.$emit('selected-row', row)
    },
    /**
     * Populates a new row and opens the row edit modal
     * to edit the row.
     */
    populateAndEditRow(row) {
      const rowClone = populateRow(clone(row))
      this.$refs.rowEditModal.show(row.id, rowClone)
    },
    /**
     * Toggles the visibility of a field in the row edit modal.
     */
    toggleTimescaleContext(event) {
      this.$refs.timescaleContext.toggle(
        event.currentTarget,
        'bottom',
        'right',
        4
      )
    },
    /**
     * Updates the timescale of the view, saving the new value in the backend if the
     * user has permission to do so. The timescale refresh happens in a watcher, so we
     * can use the optimistic update there and immediately update the view.
     */
    async updateTimescale(value) {
      this.$refs.timescaleContext.hide()

      const payload = {
        view: this.view,
        values: { timescale: value },
      }

      if (this.canChangeDateSettings) {
        try {
          await this.$store.dispatch('view/update', payload)
        } catch (error) {
          notifyIf(error, 'view')
        }
      } else {
        await this.$store.dispatch('view/forceUpdate', payload)
      }
    },
  },
}
</script>

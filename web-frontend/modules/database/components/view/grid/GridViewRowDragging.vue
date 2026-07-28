<template>
  <div
    v-show="dragging"
    ref="root"
    class="grid-view__row-dragging-container"
    :style="{ left: offset + 'px' }"
  >
    <div
      class="grid-view__row-dragging"
      :style="{ width: width + 'px', top: draggingTop + 'px' }"
    ></div>
    <div
      v-show="targetAvailable"
      class="grid-view__row-target"
      :style="{ width: width + 'px', top: targetTop + 'px' }"
    ></div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import {
  canMoveRowsAcrossGroupByFields,
  getGroupByFieldsFromActiveGroupBys,
} from '@baserow/modules/database/utils/gridGroupBy'
import {
  pathKey,
  resolveGroupByRowMoveTarget,
} from '@baserow/modules/database/utils/gridGroupByRender'

export default {
  name: 'GridViewRowDragging',
  mixins: [gridViewHelpers],
  props: {
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
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
    getScrollElement: {
      type: Function,
      required: true,
    },
    offset: {
      type: Number,
      required: false,
      default: () => 0,
    },
  },
  emits: ['scroll'],
  data() {
    return {
      // Indicates if the user is dragging a row to another position.
      dragging: false,
      // The row object that is being dragged.
      row: null,
      // The top position of the row.
      rowTop: 0,
      // The row where the dragged row must be placed before.
      targetRow: null,
      // The complete grouped insertion target, or null outside grouped mode.
      groupTarget: null,
      // Whether the pointer currently resolves to an explicit insertion slot.
      targetAvailable: false,
      // The horizontal starting position of the mouse.
      mouseStart: 0,
      // The position of the dragging animation.
      draggingTop: 0,
      // The position of the target indicator where the field is going to be moved to.
      targetTop: 0,
      // The mouse move event.
      lastMoveEvent: null,
      // Indicates if the user is auto scrolling at the moment.
      autoScrolling: false,
      // Event handler references for cleanup
      moveEvent: null,
      upEvent: null,
      keydownEvent: null,
      scrollTimeout: null,
    }
  },
  computed: {
    width() {
      return (
        this.allVisibleFields.reduce(
          (value, field) => this.getFieldWidth(field) + value,
          0
        ) + this.gridViewRowDetailsWidth
      )
    },
    rowHeight() {
      return this.$store.getters[this.storePrefix + 'view/grid/getRowHeight']
    },
    bufferStartIndex() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getBufferStartIndex'
      ]
    },
    rowsCount() {
      return this.$store.getters[this.storePrefix + 'view/grid/getCount']
    },
    allRows() {
      return this.$store.getters[this.storePrefix + 'view/grid/getAllRows']
    },
    activeGroupBys() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getActiveGroupBys'
      ]
    },
    groupByFields() {
      return getGroupByFieldsFromActiveGroupBys(
        this.activeGroupBys,
        this.allFieldsInTable
      )
    },
    isGroupByMode() {
      return this.groupByFields.length > 0
    },
    groupByLayout() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getGroupByLayout'
      ]
    },
    groupBySectionRows() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getGroupBySectionRowsMap'
      ]
    },
    sourceGroupPath() {
      if (!this.isGroupByMode || this.row === null) {
        return null
      }
      return this.$store.getters[
        this.storePrefix + 'view/grid/getGroupByRowPath'
      ](this.row.id, this.allFieldsInTable)
    },
    canMoveAcrossGroups() {
      return canMoveRowsAcrossGroupByFields(this.groupByFields, this.$registry)
    },
  },
  beforeUnmount() {
    this.cancel()
  },
  methods: {
    getRowTop(rowId) {
      if (this.isGroupByMode) {
        return (
          this.$store.getters[
            this.storePrefix + 'view/grid/getGroupByRowVerticalRange'
          ](rowId, this.allFieldsInTable)?.top || 0
        )
      }
      const index = this.allRows.findIndex((row) => row.id === rowId)
      if (index < 0) {
        return 0
      }

      return this.bufferStartIndex * this.rowHeight + index * this.rowHeight
    },
    /**
     * Called when the row dragging must start. It will register the global mouse
     * move, mouse up events and keyup events so that the user can drag the field to
     * the correct position.
     */
    start(row, event) {
      const element = this.getScrollElement()

      this.row = row
      this.startRowTop = this.getRowTop(row.id) - element.scrollTop
      this.targetRowId = row.id
      this.dragging = true
      this.groupTarget = null
      this.targetAvailable = !this.isGroupByMode
      this.mouseStart = event.clientY
      this.draggingTop = 0
      this.targetTop = 0

      this.moveEvent = (event) => this.move(event)
      window.addEventListener('mousemove', this.moveEvent)

      this.upEvent = (event) => this.up(event)
      window.addEventListener('mouseup', this.upEvent)

      this.keydownEvent = (event) => {
        if (event.key === 'Escape') {
          // When the user presses the escape key we want to cancel the action
          this.cancel(event)
        }
      }
      document.body.addEventListener('keydown', this.keydownEvent)
      this.move(event, false)
    },
    /**
     * The move method is called when every time the user moves the mouse while
     * dragging a row. It can also be called while auto scrolling.
     */
    move(event = null, startAutoScroll = true) {
      if (event !== null) {
        event.preventDefault()
        this.lastMoveEvent = event
      } else {
        event = this.lastMoveEvent
      }

      // This is the vertically scrollable element.
      const element = this.getScrollElement()
      const elementRect = element.getBoundingClientRect()
      const elementHeight = elementRect.bottom - elementRect.top

      // Calculate the top position of the dragging effect. Note that this effect lays
      // over the vertically scrollable rows.
      this.draggingTop = Math.max(
        0,
        Math.min(
          this.startRowTop + event.clientY - this.mouseStart,
          elementHeight - this.rowHeight
        )
      )

      // Calculate before which row we want to place the row that is currently being
      // dragged. We also calculate target top position which indicates at which
      // position the row is going to be placed. Note that the target effect lays over
      // the vertically scrollable rows.
      const mouseTop = event.clientY - elementRect.top + element.scrollTop
      if (this.isGroupByMode) {
        const target = resolveGroupByRowMoveTarget({
          layout: this.groupByLayout,
          sectionRows: this.groupBySectionRows,
          contentY: mouseTop,
          fields: this.groupByFields,
          sourcePath: this.sourceGroupPath,
          allowCrossGroup: this.canMoveAcrossGroups,
          rowHeight: this.rowHeight,
        })
        this.groupTarget = this.isGroupedTargetNoop(target) ? null : target
        this.targetAvailable = this.groupTarget !== null
        if (this.groupTarget !== null) {
          this.targetTop = this.groupTarget.y - element.scrollTop
          this.targetRow = this.groupTarget.before
        }
      } else {
        const rowIndex = Math.max(
          0,
          Math.min(Math.round(mouseTop / this.rowHeight), this.rowsCount)
        )
        this.targetTop = rowIndex * this.rowHeight - element.scrollTop
        const beforeRow = this.allRows[rowIndex - this.bufferStartIndex]
        this.targetRow = beforeRow === undefined ? null : beforeRow
        this.targetAvailable = true
      }

      // If the user is not already auto scrolling, which happens while dragging and
      // moving the element close to the end of the view port at the top or bottom
      // side, we might need to initiate that process.
      if (!this.autoScrolling || !startAutoScroll) {
        const side = Math.ceil((elementHeight / 100) * 10)
        const autoScrollMouseTop = event.clientY - elementRect.top
        const autoScrollMouseBottom = elementHeight - autoScrollMouseTop
        let speed = 0

        if (autoScrollMouseTop < side) {
          speed = -(6 - Math.ceil((Math.max(0, autoScrollMouseTop) / side) * 6))
        } else if (autoScrollMouseBottom < side) {
          speed = 6 - Math.ceil((Math.max(0, autoScrollMouseBottom) / side) * 6)
        }

        // If the speed is either a position or negative, so not 0, we know that we
        // need to start auto scrolling.
        if (speed !== 0) {
          this.autoScrolling = true
          this.$emit('scroll', { pixelY: speed, pixelX: 0 })
          this.scrollTimeout = setTimeout(() => {
            this.move(null, false)
          }, 1)
        } else {
          this.autoScrolling = false
        }
      }
    },
    /**
     * Can be called when the current dragging state needs to be stopped. It will
     * remove all the created event listeners and timeouts.
     */
    cancel() {
      this.dragging = false
      window.removeEventListener('mousemove', this.moveEvent)
      window.removeEventListener('mouseup', this.upEvent)
      document.body.removeEventListener('keydown', this.keydownEvent)
      clearTimeout(this.scrollTimeout)
    },
    isGroupedTargetNoop(target) {
      if (target === null || this.sourceGroupPath === null) {
        return false
      }
      const sourceSectionKey = pathKey(this.sourceGroupPath, this.groupByFields)
      if (target.sectionKey !== sourceSectionKey) {
        return false
      }
      const sourceRows = this.groupBySectionRows.get(sourceSectionKey)
      const sourcePosition = [...(sourceRows?.entries() || [])].find(
        ([, row]) => row.id === this.row.id
      )?.[0]
      return (
        sourcePosition !== undefined &&
        (target.position === sourcePosition ||
          target.position === sourcePosition + 1)
      )
    },
    /**
     * Called when the user releases the mouse on a the desired position. It will
     * calculate the new position of the row in the list and if it has changed
     * position, then the order in the row options is updated accordingly.
     */
    async up(event) {
      event.preventDefault()
      this.cancel()

      if (!this.targetAvailable) {
        return
      }

      // We don't need to do anything if the row must be placed before or after itself
      // because that wouldn't change the position.
      if (!this.isGroupByMode && this.targetRow !== null) {
        // If the row must be placed before itself.
        if (this.row.id === this.targetRow.id) {
          return
        }

        // If the row needs to be placed after itself.
        const allRows =
          this.$store.getters[this.storePrefix + 'view/grid/getAllRows']
        const index = allRows.findIndex((r) => r.id === this.targetRow.id)
        const after = allRows[index - 1]
        if (after && this.row.id === after.id) {
          return
        }
      }

      const element = this.getScrollElement()
      const getScrollTop = () => element.scrollTop

      try {
        await this.$store.dispatch(this.storePrefix + 'view/grid/moveRow', {
          table: this.table,
          grid: this.view,
          fields: this.allFieldsInTable,
          getScrollTop,
          row: this.row,
          before: this.targetRow,
          sourceGroupPath: this.sourceGroupPath,
          targetGroupPath: this.groupTarget?.path || null,
        })
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
  },
}
</script>

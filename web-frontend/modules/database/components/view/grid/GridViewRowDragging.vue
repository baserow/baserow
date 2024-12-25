<template>
  <div
    v-show="dragging"
    class="grid-view__row-dragging-container"
    :style="{ left: offset + 'px' }"
  >
    <div
      class="grid-view__row-dragging"
      :style="{ width: width + 'px', top: draggingTop + 'px' }"
    ></div>
    <div
      class="grid-view__row-target"
      :style="{ width: width + 'px', top: targetTop + 'px' }"
    ></div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'

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
    vertical: {
      type: String,
      required: true,
    },
    offset: {
      type: Number,
      required: false,
      default: () => 0,
    },
  },
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
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        rowHeight:
          this.$options.propsData.storePrefix + 'view/grid/getRowHeight',
        bufferStartIndex:
          this.$options.propsData.storePrefix + 'view/grid/getBufferStartIndex',
        rowsCount: this.$options.propsData.storePrefix + 'view/grid/getCount',
        allRows: this.$options.propsData.storePrefix + 'view/grid/getAllRows',
      }),
    }
  },
  beforeDestroy() {
    this.cancel()
  },
  methods: {
    getRowTop(rowId) {
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
      const element = this.$parent[this.vertical]()

      this.row = row
      this.startRowTop = this.getRowTop(row.id) - element.scrollTop
      this.targetRowId = row.id
      this.dragging = true
      this.mouseStart = event.clientY
      this.draggingTop = 0
      this.targetTop = 0

      this.$el.moveEvent = (event) => this.move(event)
      window.addEventListener('mousemove', this.$el.moveEvent)

      this.$el.upEvent = (event) => this.up(event)
      window.addEventListener('mouseup', this.$el.upEvent)

      this.$el.keydownEvent = (event) => {
        if (event.key === 'Escape') {
          // When the user presses the escape key we want to cancel the action
          this.cancel(event)
        }
      }
      document.body.addEventListener('keydown', this.$el.keydownEvent)
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
      const element = this.$parent[this.vertical]()
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
      const rowIndex = Math.max(
        0,
        Math.min(Math.round(mouseTop / this.rowHeight), this.rowsCount)
      )
      this.targetTop = rowIndex * this.rowHeight - element.scrollTop
      const beforeRow = this.allRows[rowIndex - this.bufferStartIndex]
      this.targetRow = beforeRow === undefined ? null : beforeRow

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
          this.$el.scrollTimeout = setTimeout(() => {
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
      window.removeEventListener('mousemove', this.$el.moveEvent)
      window.removeEventListener('mouseup', this.$el.upEvent)
      document.body.addEventListener('keydown', this.$el.keydownEvent)
      clearTimeout(this.$el.scrollTimeout)
    },
    /**
     * Called when the user releases the mouse on a the desired position. It will
     * calculate the new position of the row in the list and if it has changed
     * position, then the order in the row options is updated accordingly.
     */
    async up(event) {
      event.preventDefault()
      this.cancel()

      // We don't need to do anything if the row must be placed before or after itself
      // because that wouldn't change the position.
      if (this.targetRow !== null) {
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

      const element = this.$parent[this.vertical]()
      const getScrollTop = () => element.scrollTop

      try {
        await this.$store.dispatch(this.storePrefix + 'view/grid/moveRow', {
          table: this.table,
          grid: this.view,
          fields: this.allFieldsInTable,
          getScrollTop,
          row: this.row,
          before: this.targetRow,
        })
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
  },
}
</script>

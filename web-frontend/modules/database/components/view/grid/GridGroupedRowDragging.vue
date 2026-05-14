<template>
  <div
    v-show="dragging"
    class="grid-view__row-dragging-container grid-grouped__row-dragging-container"
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

<style lang="scss" scoped>
// The flat grid mounts its row-dragging container in a non-scrolling
// overlay, so the shared `.grid-view__row-dragging-container` styles
// subtract the head/foot heights. We mount inside the canvas itself
// (which already excludes the head/foot), so override both the box
// and reset top/bottom — the indicator children use canvas-y coords
// directly.
.grid-grouped__row-dragging-container {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: visible;
}
</style>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { pathKey } from '@baserow/modules/database/utils/gridGroupedRender'

const AUTO_SCROLL_EDGE_RATIO = 0.1
const AUTO_SCROLL_MAX_SPEED = 6

export default {
  name: 'GridGroupedRowDragging',
  props: {
    table: { type: Object, required: true },
    view: { type: Object, required: true },
    storePrefix: { type: String, default: 'page/' },
    width: { type: Number, required: true },
    visibleItems: { type: Array, required: true },
    allFieldsInTable: { type: Array, default: () => [] },
    getScrollElement: { type: Function, required: true },
  },
  emits: ['scroll'],
  data() {
    return {
      dragging: false,
      row: null,
      sourceSectionKey: null,
      pickupOffsetInRow: 0,
      sourceRowY: 0,
      draggingTop: 0,
      targetTop: 0,
      mouseStart: 0,
      targetBeforeRowId: null,
      targetSectionPath: null,
      targetSectionKey: null,
      lastMoveEvent: null,
      autoScrolling: false,
      moveListener: null,
      upListener: null,
      keyListener: null,
      scrollTimeout: null,
    }
  },
  computed: {
    storeNs() {
      return this.storePrefix + 'view/gridGrouped'
    },
    groupByFields() {
      return this.$store.getters[this.storeNs + '/groupByFields']
    },
    rowItems() {
      return this.visibleItems.filter((it) => it.type === 'row')
    },
  },
  beforeUnmount() {
    this.cancel()
  },
  methods: {
    /**
     * Start a drag for `row` from `event` (the mousedown on the row's
     * drag handle). Constrains the drop targets to the row's own
     * section by reading the layout's row items for that section.
     */
    start(row, event) {
      const sourceItem = this.visibleItems.find(
        (it) => it.type === 'row' && it.row?.id === row.id
      )
      if (!sourceItem) return
      this.row = row
      this.sourceSectionKey = pathKey(sourceItem.path, this.groupByFields)
      // All coordinates inside the dragging container are canvas-y
      // (absolute within the scrollable canvas), since the container
      // is mounted inside the canvas itself.
      this.sourceRowY = sourceItem.y
      const element = this.getScrollElement()
      const elementRect = element.getBoundingClientRect()
      const mouseYInCanvas =
        event.clientY - elementRect.top + element.scrollTop
      this.pickupOffsetInRow = mouseYInCanvas - sourceItem.y
      this.mouseStart = event.clientY
      this.dragging = true
      this.draggingTop = sourceItem.y
      // Anchor the drop indicator on the source row's top edge until
      // the mouse has actually moved. Without this, the initial
      // `move()` would snap to whichever edge of the row the mouse
      // happens to be closest to (the drag handle sits in the bottom
      // half), so releasing without moving would swap the row with
      // its neighbour below.
      this.targetTop = sourceItem.y
      this.targetBeforeRowId = row.id
      this.targetSectionPath = sourceItem.path
      this.targetSectionKey = this.sourceSectionKey

      this.moveListener = (e) => this.move(e)
      this.upListener = (e) => this.up(e)
      this.keyListener = (e) => {
        if (e.key === 'Escape') this.cancel()
      }
      window.addEventListener('mousemove', this.moveListener)
      window.addEventListener('mouseup', this.upListener)
      document.body.addEventListener('keydown', this.keyListener)
    },
    move(event = null, startAutoScroll = true) {
      if (event) {
        event.preventDefault()
        this.lastMoveEvent = event
      } else {
        event = this.lastMoveEvent
      }
      if (!event) return

      const element = this.getScrollElement()
      const elementRect = element.getBoundingClientRect()
      const elementHeight = elementRect.bottom - elementRect.top
      const canvasHeight = element.scrollHeight
      const rowHeight =
        this.$store.getters[this.storeNs + '/rowHeight'] ?? 33

      const mouseYInCanvas =
        event.clientY - elementRect.top + element.scrollTop

      // Float the drag preview where the user's cursor sits in the
      // canvas, offset by where in the source row they originally
      // grabbed. Clamp inside the canvas bounds so the preview can't
      // float past the top or bottom.
      this.draggingTop = Math.max(
        0,
        Math.min(
          mouseYInCanvas - this.pickupOffsetInRow,
          canvasHeight - rowHeight
        )
      )

      // Direction-aware drop target: find the row the cursor is
      // *inside* (or above/below) and let the source row's position
      // relative to that row decide which side of it to drop into.
      // This way ANY upward drag into a row above the source moves
      // the source up; ANY downward drag into a row below the
      // source moves it down — without forcing the user to cross
      // each row's vertical centre.
      const items = this.rowItems
      const sectionKeyOf = (it) => pathKey(it.path, this.groupByFields)

      // Find the row item under (or nearest to) the cursor.
      let under = null
      for (const item of items) {
        if (mouseYInCanvas < item.y) break
        under = item
        if (mouseYInCanvas < item.y + item.height) break
      }
      if (!under) under = items[0]
      if (!under) return

      const underKey = sectionKeyOf(under)
      const underIndex = items.indexOf(under)
      const sourceIndex = items.findIndex((it) => it.row?.id === this.row.id)
      const underIsSource = under.row.id === this.row.id

      let best
      if (underIsSource || sourceIndex < 0) {
        best = {
          y: under.y,
          beforeRowId: this.row.id,
          path: under.path,
          sectionKey: underKey,
        }
      } else if (underIndex < sourceIndex) {
        // Cursor on a row above the source: drop *above* that row.
        best = {
          y: under.y,
          beforeRowId: under.row.id,
          path: under.path,
          sectionKey: underKey,
        }
      } else {
        // Cursor on a row below the source: drop *below* that row.
        // The "before" row is the next row in the same section;
        // null means we're dropping at the end of the section.
        const next = items[underIndex + 1]
        const nextInSection = next && sectionKeyOf(next) === underKey
        best = {
          y: under.y + under.height,
          beforeRowId: nextInSection ? next.row.id : null,
          path: under.path,
          sectionKey: underKey,
        }
      }
      this.targetTop = best.y
      this.targetBeforeRowId = best.beforeRowId
      this.targetSectionPath = best.path
      this.targetSectionKey = best.sectionKey

      if (!this.autoScrolling || !startAutoScroll) {
        const edge = Math.ceil(elementHeight * AUTO_SCROLL_EDGE_RATIO)
        const mouseTop = event.clientY - elementRect.top
        const mouseBottom = elementHeight - mouseTop
        let speed = 0
        if (mouseTop < edge) {
          speed = -(
            AUTO_SCROLL_MAX_SPEED -
            Math.ceil((Math.max(0, mouseTop) / edge) * AUTO_SCROLL_MAX_SPEED)
          )
        } else if (mouseBottom < edge) {
          speed =
            AUTO_SCROLL_MAX_SPEED -
            Math.ceil((Math.max(0, mouseBottom) / edge) * AUTO_SCROLL_MAX_SPEED)
        }
        if (speed !== 0) {
          this.autoScrolling = true
          this.$emit('scroll', speed)
          this.scrollTimeout = setTimeout(() => {
            this.move(null, false)
          }, 1)
        } else {
          this.autoScrolling = false
        }
      }
    },
    cancel() {
      this.dragging = false
      if (this.moveListener)
        window.removeEventListener('mousemove', this.moveListener)
      if (this.upListener)
        window.removeEventListener('mouseup', this.upListener)
      if (this.keyListener)
        document.body.removeEventListener('keydown', this.keyListener)
      clearTimeout(this.scrollTimeout)
      this.autoScrolling = false
    },
    async up(event) {
      event.preventDefault()
      const row = this.row
      const beforeRowId = this.targetBeforeRowId
      const targetSectionKey = this.targetSectionKey
      const targetSectionPath = this.targetSectionPath
      const sourceSectionKey = this.sourceSectionKey
      this.cancel()
      if (!row) return
      // No-op: drop on the source row itself. `start()` initialises
      // `targetBeforeRowId = row.id`, and `move()` only changes it
      // once the user actually moves the cursor far enough to land
      // on a different row's edge — so a plain click-and-release
      // hits this branch and exits without dispatching.
      if (beforeRowId === row.id) return
      try {
        if (
          targetSectionKey &&
          targetSectionKey !== sourceSectionKey &&
          targetSectionPath
        ) {
          await this.$store.dispatch(this.storeNs + '/moveRowToSection', {
            table: this.table,
            view: this.view,
            fields: this.allFieldsInTable,
            row,
            targetPath: targetSectionPath,
          })
        } else {
          await this.$store.dispatch(this.storeNs + '/moveRow', {
            table: this.table,
            rowId: row.id,
            beforeRowId,
          })
        }
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
  },
}
</script>

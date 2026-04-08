<template>
  <div
    class="grid-view__freeze-handle"
    :class="{
      'grid-view__freeze-handle--dragging': dragging,
    }"
    :style="[handleStyle, mouseButtonDown ? { pointerEvents: 'none' } : {}]"
    @mousedown.stop="startDrag"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
    @mousemove="onHoverMove"
  >
    <div
      v-if="hovering || dragging"
      class="grid-view__freeze-handle-grip"
      :style="gripStyle"
    ></div>
    <div
      v-if="dragging && snapLineOffset !== null"
      class="grid-view__freeze-snap-line"
      :style="snapLineStyle"
    ></div>
    <div
      v-if="hovering || dragging"
      class="grid-view__freeze-handle-tooltip"
      :style="tooltipStyle"
    >
      {{ dragging ? tooltipText : $t('gridViewFreezeHandle.hoverHint') }}
    </div>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  filterVisibleFieldsFunction,
  sortFieldsByOrderAndIdFunction,
} from '@baserow/modules/database/utils/view'

const MAX_FROZEN_COLUMNS = 4
const HANDLE_PADDING = 20

export default {
  name: 'GridViewFreezeHandle',
  props: {
    view: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    fieldOptions: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    /**
     * The width of the row details column (row number / expand icon) that
     * offsets all fields from the left edge.
     */
    rowDetailsWidth: {
      type: Number,
      required: true,
    },
    getFieldWidth: {
      type: Function,
      required: true,
    },
    /**
     * The default left position of the handle (the current frozen section width).
     * Overridden during drag to follow the cursor freely.
     */
    leftWidth: {
      type: Number,
      required: true,
    },
  },
  emits: ['frozen-count-change'],
  data() {
    return {
      dragging: false,
      hovering: false,
      dragFrozenCount: null,
      dragMouseX: null,
      dragMouseY: null,
      hoverMouseY: null,
      snapLineOffset: null,
      mouseButtonDown: false,
    }
  },
  computed: {
    currentFrozenCount() {
      return this.view.frozen_column_count ?? 1
    },
    sortedFields() {
      return this.fields
        .slice()
        .filter(filterVisibleFieldsFunction(this.fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(this.fieldOptions, true))
    },
    maxFrozenColumns() {
      return Math.min(this.sortedFields.length, MAX_FROZEN_COLUMNS)
    },
    tooltipText() {
      const count = this.dragFrozenCount ?? this.currentFrozenCount
      return this.$t('gridViewFreezeHandle.freeze', { count })
    },
    /**
     * During drag, the handle follows the mouse freely.
     * Otherwise, use leftWidth from the parent.
     */
    handleStyle() {
      if (this.dragging && this.dragMouseX !== null) {
        return { left: this.dragMouseX + 'px' }
      }
      return { left: this.leftWidth + 'px' }
    },
    gripStyle() {
      const y = this.dragging ? this.dragMouseY : this.hoverMouseY
      if (y === null) return { top: '50px' }
      // Grip is 18px tall, center it on the cursor Y. Clamp to stay visible.
      const clamped = Math.max(0, y - 9)
      return { top: clamped + 'px' }
    },
    tooltipStyle() {
      const y = this.dragging ? this.dragMouseY : this.hoverMouseY
      if (y === null) return {}
      return { top: y - 10 + 'px', left: '16px', transform: 'none' }
    },
    snapLineStyle() {
      if (this.snapLineOffset === null) return {}
      return { left: this.snapLineOffset + 'px' }
    },
  },
  mounted() {
    this._onGlobalMouseDown = (e) => {
      // Ignore clicks on the handle itself — those trigger startDrag.
      if (this.$el.contains(e.target)) return
      this.mouseButtonDown = true
      this.hovering = false
      this.hoverMouseY = null
    }
    this._onGlobalMouseUp = () => {
      this.mouseButtonDown = false
    }
    window.addEventListener('mousedown', this._onGlobalMouseDown)
    window.addEventListener('mouseup', this._onGlobalMouseUp)
  },
  beforeUnmount() {
    window.removeEventListener('mousedown', this._onGlobalMouseDown)
    window.removeEventListener('mouseup', this._onGlobalMouseUp)
  },
  methods: {
    getFieldBoundaries() {
      const boundaries = []
      let cumulative = this.rowDetailsWidth
      for (const field of this.sortedFields) {
        cumulative += this.getFieldWidth(field)
        boundaries.push(cumulative)
      }
      return boundaries
    },
    nearestBoundaryCount(x, boundaries) {
      // Count 0 snaps to the row-details right edge (no frozen columns).
      let bestCount = 0
      let bestDist = Math.abs(x - this.rowDetailsWidth)
      for (let i = 0; i < boundaries.length && i < this.maxFrozenColumns; i++) {
        const dist = Math.abs(x - boundaries[i])
        if (dist < bestDist) {
          bestDist = dist
          bestCount = i + 1
        }
      }
      return bestCount
    },
    onMouseEnter(e) {
      // Don't show hover visuals if a mouse button is pressed (e.g. multi-select).
      if (e.buttons !== 0) return
      this.hovering = true
    },
    onMouseLeave() {
      this.hovering = false
      this.hoverMouseY = null
    },
    onHoverMove(e) {
      if (this.dragging) return
      // Hide if a button was pressed while hovering (e.g. started selecting cells).
      if (e.buttons !== 0) {
        this.hovering = false
        this.hoverMouseY = null
        return
      }
      const rect = this.$el.getBoundingClientRect()
      this.hoverMouseY = e.clientY - rect.top
    },
    startDrag(event) {
      event.preventDefault()
      this.dragging = true
      this.dragFrozenCount = this.currentFrozenCount

      const boundaries = this.getFieldBoundaries()
      const validBoundaries = boundaries.slice(0, this.maxFrozenColumns)

      // Set initial drag position to current handle position
      this.dragMouseX = this.leftWidth

      const gridEl = this.$el.closest('.grid-view')

      const onMove = (e) => {
        e.preventDefault()
        if (!gridEl) return
        const gridRect = gridEl.getBoundingClientRect()
        const relativeX = e.clientX - gridRect.left

        // Clamp X within valid range
        const minX = this.rowDetailsWidth
        const maxX =
          validBoundaries.length > 0
            ? validBoundaries[validBoundaries.length - 1] + HANDLE_PADDING
            : minX + HANDLE_PADDING
        this.dragMouseX = Math.max(minX, Math.min(relativeX, maxX))

        // Track Y relative to the handle element
        const handleRect = this.$el.getBoundingClientRect()
        this.dragMouseY = e.clientY - handleRect.top

        // Determine nearest boundary and if we're close to it
        const newCount = this.nearestBoundaryCount(
          this.dragMouseX,
          validBoundaries
        )
        const snapX =
          newCount === 0 ? this.rowDetailsWidth : validBoundaries[newCount - 1]

        // Show the snap preview line at the boundary position, offset from
        // the handle's current left. Compensate for the handle's -6px margin.
        // Only show when NOT already on the boundary.
        if (this.dragMouseX !== snapX) {
          this.snapLineOffset = snapX - this.dragMouseX + 6
        } else {
          this.snapLineOffset = null
        }

        if (newCount !== this.dragFrozenCount) {
          this.dragFrozenCount = newCount
        }
      }

      const onUp = (e) => {
        e.preventDefault()
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
        document.body.classList.remove('resizing-horizontal')
        document.body.classList.remove('grid-view--disable-selection')

        const finalCount = this.nearestBoundaryCount(
          this.dragMouseX,
          validBoundaries
        )

        this.dragging = false
        this.dragFrozenCount = null
        this.dragMouseX = null
        this.dragMouseY = null
        this.snapLineOffset = null

        if (finalCount !== this.currentFrozenCount) {
          this.$emit('frozen-count-change', finalCount)
          this.saveFrozenCount(finalCount)
        }
      }

      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
      document.body.classList.add('resizing-horizontal')
      document.body.classList.add('grid-view--disable-selection')
    },
    async saveFrozenCount(count) {
      try {
        await this.$store.dispatch('view/update', {
          view: this.view,
          values: { frozen_column_count: count },
          readOnly:
            this.readOnly ||
            !this.$hasPermission(
              'database.table.view.update',
              this.view,
              this.database.workspace.id
            ),
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>

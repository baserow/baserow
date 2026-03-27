<template>
  <div
    class="grid-view__freeze-handle"
    :class="{
      'grid-view__freeze-handle--dragging': dragging,
      'grid-view__freeze-handle--near-boundary': nearBoundary,
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
const SNAP_THRESHOLD = 20

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
      nearBoundary: false,
      snapLineOffset: null,
      mouseButtonDown: false,
    }
  },
  computed: {
    currentFrozenCount() {
      return this.view.frozen_column_count || 1
    },
    sortedFields() {
      return this.fields
        .slice()
        .filter(filterVisibleFieldsFunction(this.fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(this.fieldOptions, true))
    },
    maxFrozenColumns() {
      // Ensure at least one field remains in the scrollable section.
      return Math.min(
        Math.max(this.sortedFields.length - 1, 1),
        MAX_FROZEN_COLUMNS
      )
    },
    tooltipText() {
      const count = this.dragFrozenCount ?? this.currentFrozenCount
      if (count === 1) {
        return this.$t('gridViewFreezeHandle.freezeOne')
      }
      return this.$t('gridViewFreezeHandle.freezeN', { count })
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
      return { top: y + 16 + 'px' }
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
      let bestCount = 1
      let bestDist = Infinity
      for (let i = 0; i < boundaries.length && i < this.maxFrozenColumns; i++) {
        const dist = Math.abs(x - boundaries[i])
        if (dist < bestDist) {
          bestDist = dist
          bestCount = i + 1
        }
      }
      return bestCount
    },
    isNearBoundary(x, boundaries) {
      for (let i = 0; i < boundaries.length && i < this.maxFrozenColumns; i++) {
        if (Math.abs(x - boundaries[i]) <= SNAP_THRESHOLD) {
          return true
        }
      }
      return false
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
            ? validBoundaries[validBoundaries.length - 1] + 50
            : minX + 50
        this.dragMouseX = Math.max(minX, Math.min(relativeX, maxX))

        // Track Y relative to the handle element
        const handleRect = this.$el.getBoundingClientRect()
        this.dragMouseY = e.clientY - handleRect.top

        // Determine nearest boundary and if we're close to it
        const newCount = this.nearestBoundaryCount(
          this.dragMouseX,
          validBoundaries
        )
        const snapX = validBoundaries[newCount - 1]
        this.nearBoundary = Math.abs(this.dragMouseX - snapX) <= SNAP_THRESHOLD

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

        const finalCount = this.nearestBoundaryCount(
          this.dragMouseX,
          validBoundaries
        )

        this.dragging = false
        this.dragFrozenCount = null
        this.dragMouseX = null
        this.dragMouseY = null
        this.nearBoundary = false
        this.snapLineOffset = null

        if (finalCount !== this.currentFrozenCount) {
          this.$emit('frozen-count-change', finalCount)
          this.saveFrozenCount(finalCount)
        }
      }

      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
      document.body.classList.add('resizing-horizontal')
    },
    async saveFrozenCount(count) {
      const value = count <= 1 ? null : count
      try {
        await this.$store.dispatch('view/update', {
          view: this.view,
          values: { frozen_column_count: value },
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

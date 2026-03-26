<template>
  <div
    class="grid-view__freeze-handle"
    :class="{ 'grid-view__freeze-handle--dragging': dragging }"
    :style="handleStyle"
    @mousedown.stop="startDrag"
    @mouseenter="hovering = true"
    @mouseleave="hovering = false"
  >
    <div
      v-if="hovering || dragging"
      class="grid-view__freeze-handle-icon"
    ></div>
    <div v-if="dragging" class="grid-view__freeze-handle-tooltip">
      {{ tooltipText }}
    </div>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { sortFieldsByOrderAndIdFunction } from '@baserow/modules/database/utils/view'

const MAX_FROZEN_COLUMNS = 4

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
     * Overridden during drag to snap to field boundaries.
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
      dragSnapLeft: null,
    }
  },
  computed: {
    currentFrozenCount() {
      return this.view.frozen_column_count || 1
    },
    sortedFields() {
      return this.fields
        .slice()
        .sort(sortFieldsByOrderAndIdFunction(this.fieldOptions, true))
    },
    maxFrozenColumns() {
      return Math.min(this.sortedFields.length - 1, MAX_FROZEN_COLUMNS)
    },
    tooltipText() {
      const count = this.dragFrozenCount ?? this.currentFrozenCount
      if (count === 1) {
        return this.$t('gridViewFreezeHandle.freezeOne')
      }
      return this.$t('gridViewFreezeHandle.freezeN', { count })
    },
    /**
     * During drag, snap the handle to the field boundary for dragFrozenCount.
     * Otherwise, use leftWidth from the parent.
     */
    handleStyle() {
      if (this.dragging && this.dragSnapLeft !== null) {
        return { left: this.dragSnapLeft + 'px' }
      }
      return { left: this.leftWidth + 'px' }
    },
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
    countFromX(clientX, boundaries) {
      let count = 1
      for (let i = 0; i < boundaries.length; i++) {
        const prevEdge = i === 0 ? this.rowDetailsWidth : boundaries[i - 1]
        const midpoint = prevEdge + (boundaries[i] - prevEdge) / 2
        if (clientX > midpoint) {
          count = i + 1
        }
      }
      return Math.max(1, Math.min(count, this.maxFrozenColumns))
    },
    startDrag(event) {
      event.preventDefault()
      this.dragging = true
      this.dragFrozenCount = this.currentFrozenCount

      const boundaries = this.getFieldBoundaries()
      // Set initial snap position
      this.dragSnapLeft = boundaries[this.dragFrozenCount - 1] || boundaries[0]

      const onMove = (e) => {
        e.preventDefault()
        const gridEl = this.$el.closest('.grid-view')
        const gridRect = gridEl.getBoundingClientRect()
        const relativeX = e.clientX - gridRect.left
        const newCount = this.countFromX(relativeX, boundaries)
        // Always update snap position to follow the cursor to field boundaries
        this.dragSnapLeft = boundaries[newCount - 1] || boundaries[0]
        if (newCount !== this.dragFrozenCount) {
          this.dragFrozenCount = newCount
          this.$emit('frozen-count-change', newCount)
        }
      }

      const onUp = (e) => {
        e.preventDefault()
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
        document.body.classList.remove('resizing-horizontal')

        const finalCount = this.dragFrozenCount
        this.dragging = false
        this.dragFrozenCount = null
        this.dragSnapLeft = null

        if (finalCount !== this.currentFrozenCount) {
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

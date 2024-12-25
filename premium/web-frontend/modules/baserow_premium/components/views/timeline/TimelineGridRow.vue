<template>
  <div :style="{ height: '100%' }">
    <div
      v-if="deltaLeft || deltaWidth"
      :style="{
        left: `${left + padLeft}px`,
        width: `${width - padWidth}px`,
      }"
      class="timeline-grid-row timeline-grid-row--shadow"
    ></div>
    <div
      class="timeline-grid-row"
      :class="{
        [`background-color--${backgroundColor || 'white'}`]: true,
        'timeline-grid-row--tiny': tooTiny,
      }"
      :style="rowStyle"
      @mousedown="start"
      @mouseup="!resizing ? up : null"
      @mouseover="hovering = true"
      @mouseleave="hovering = false"
    >
      <template v-if="!tooTiny">
        <div
          v-if="leftBorderColor"
          class="left-border-decorator"
          :class="`background-color--${leftBorderColor}`"
        ></div>
        <div v-else class="timeline-grid-row__spacer"></div>
      </template>

      <div
        v-tooltip="tooltipText"
        class="timeline-grid-row__label-container"
        :class="{ 'timeline-grid-row__label-container--tiny': tooTiny }"
        tooltip-position="bottom-cursor"
      >
        <div class="timeline-grid-row__label">
          {{ label }}
        </div>
      </div>

      <div v-if="!tooTiny" class="timeline-grid-row__spacer"></div>

      <HorizontalResize
        v-show="!startDateFieldReadOnly && hovering && !dragging && !tooTiny"
        class="timeline-grid-row__resize-handle timeline-grid-row__resize-handle--start"
        :class="{
          'timeline-grid-row__resize-handle--white': backgroundColor === 'gray',
        }"
        :width="0"
        :min="-Infinity"
        :stop-propagation="true"
        @move="moveRowDate({ pos: 'start', resize: { width: $event } })"
        @update="updateRowDate({ pos: 'start', resize: $event })"
      >
      </HorizontalResize>

      <HorizontalResize
        v-show="!endDateFieldReadOnly && hovering && !dragging && !tooTiny"
        class="timeline-grid-row__resize-handle timeline-grid-row__resize-handle--end"
        :class="{
          'timeline-grid-row__resize-handle--white': backgroundColor === 'gray',
        }"
        :width="0"
        :min="-Infinity"
        :stop-propagation="true"
        @move="moveRowDate({ pos: 'end', resize: { width: $event } })"
        @update="updateRowDate({ pos: 'end', resize: $event })"
      ></HorizontalResize>
    </div>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import HorizontalResize from '@baserow/modules/core/components/HorizontalResize'

export default {
  name: 'TimelineGridRow',
  components: { HorizontalResize },
  props: {
    label: {
      type: String,
      required: true,
    },
    startDate: {
      type: String,
      default: null,
    },
    endDate: {
      type: String,
      default: null,
    },
    timezone: {
      type: String,
      required: true,
    },
    startDateFieldReadOnly: {
      type: Boolean,
      required: true,
    },
    endDateFieldReadOnly: {
      type: Boolean,
      required: true,
    },
    // use to decide if include the end date in the duration calculation
    dateOnlyFields: {
      type: Boolean,
      default: false,
    },
    leftBorderColor: {
      type: String,
      default: null,
    },
    backgroundColor: {
      type: String,
      default: null,
    },
    scrollLeft: {
      type: Number,
      default: 0,
    },
    left: {
      type: Number,
      required: true,
    },
    width: {
      type: Number,
      required: true,
    },
    leftPadding: {
      type: Number,
      default: 2,
    },
    rightPadding: {
      type: Number,
      default: 3,
    },
    minWidth: {
      type: Number,
      default: 0,
    },
    step: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      hovering: false,
      resizing: false,
      dragging: false,
      startOffset: 0,
      endOffset: 0,
      initialScrollLeft: 0,
    }
  },
  computed: {
    tooTiny() {
      return this.width < this.minWidth
    },
    rowStyle() {
      const style = {
        left: `${this.left + this.deltaLeft + this.padLeft}px`,
      }
      if (!this.tooTiny) {
        style.width = `${this.width + this.deltaWidth - this.padWidth}px`
      }
      return style
    },
    tooltipText() {
      if (
        !this.startMoment ||
        !this.endMoment ||
        this.resizing ||
        this.dragging
      ) {
        return null
      }

      let start, end
      if (this.startMoment.isSame(this.endMoment, 'year')) {
        const format = this.dateOnlyFields ? 'MMM D' : 'MMM D, HH:mm'
        start = this.startMoment.format(format)
        end = this.endMoment.format(format)
      } else {
        const format = this.dateOnlyFields
          ? 'MMM D, YYYY'
          : 'MMM D, YYYY, HH:mm'
        start = this.startMoment.format(format)
        end = this.endMoment.format(format)
      }
      let count = this.endMoment.diff(this.startMoment, 'days')
      if (this.dateOnlyFields) {
        count += 1
      }
      const duration = this.$tc('timelineGridRow.days', count, { count })
      const label = this.tooTiny ? `${this.label} | ` : ''
      return `${label}${start} - ${end} (${duration})`
    },
    startMoment() {
      return this.startDate ? moment(this.startDate).tz(this.timezone) : null
    },
    endMoment() {
      return this.endDate ? moment(this.endDate).tz(this.timezone) : null
    },
    padLeft() {
      return this.leftPadding
    },
    padWidth() {
      return this.rightPadding + this.leftPadding
    },
    deltaLeft() {
      return this.startOffset
    },
    deltaWidth() {
      return this.endOffset - this.startOffset
    },
  },
  watch: {
    startDate() {
      this.startOffset = 0
      this.endOffset = 0
    },
    endDate() {
      this.startOffset = 0
      this.endOffset = 0
    },
    scrollLeft(newValue, oldValue) {
      const delta = newValue - oldValue
      if (this.resizing) {
        if (this.startOffset > 0) {
          this.startOffset += delta
        }
        if (this.endOffset > 0) {
          this.endOffset += delta
        }
      } else if (this.dragging) {
        this.startOffset += delta
        this.endOffset += delta
      }
    },
  },
  methods: {
    /**
     * Moves the start or end date of the row by setting an offset that is used to
     * calculate the new width abd the new left offset of the row.
     * It also emits an event to notify the parent that the row is being updated so
     * it can activate the autoscrolling.
     */
    moveRowDate({ pos, resize }) {
      if (!this.resizing) {
        this.resizing = true
        this.initialScrollLeft = this.scrollLeft
        this.$emit('updating-row', true)
      }

      const deltaScroll = this.scrollLeft - this.initialScrollLeft
      const deltaWidth = resize.width + deltaScroll
      const newWidth = this.width + (pos === 'start' ? -deltaWidth : deltaWidth)

      if (newWidth < this.minWidth) {
        // Prevent resizing below the minimum width
      } else if (pos === 'start') {
        this.startOffset = deltaWidth
      } else {
        this.endOffset = deltaWidth
      }
    },
    /**
     * Stops the resizing and updates the row.
     */
    updateRowDate() {
      this.$emit('updating-row', false)
      this.updateRow()
      this.resizing = false
    },
    /**
     * Updates the start or end date of the row by emitting an event that contains the
     * final start and end offset of the row. It's up to the parent to transform these
     * offsets to actual dates.
     */
    updateRow() {
      // round the offset to the nearest column
      this.startOffset = Math.round(this.startOffset / this.step) * this.step
      this.endOffset = Math.round(this.endOffset / this.step) * this.step

      this.$emit('update-row', {
        startOffset: this.startOffset,
        endOffset: this.endOffset,
      })
    },
    /**
     * Starts the dragging of the row. The dragging is used to move the row to a different
     * position in the timeline.
     */
    start(event) {
      event.preventDefault()
      event.stopPropagation()

      this.mouseStart = event.clientX

      const readOnly = this.startDateFieldReadOnly || this.endDateFieldReadOnly
      if (!readOnly) {
        this.$el.moveEvent = (event) => this.move(event)
        window.addEventListener('mousemove', this.$el.moveEvent)
      }

      this.$el.upEvent = (event) => this.up(event)
      window.addEventListener('mouseup', this.$el.upEvent)
    },
    /**
     * Moves the row to a different position in the timeline by setting an offset that
     * is used to calculate the new left offset of the row. The offset are used to
     * recalculate the start and end date of the row, but the change is not applied
     * until the dragging is stopped.
     */
    move(event) {
      event.preventDefault()

      const deltaX = event.clientX - this.mouseStart
      if (!this.dragging) {
        // Require a minimum delta to start dragging
        if (Math.abs(deltaX) < 5) {
          return
        }

        this.dragging = true
        this.$emit('updating-row', true)
        this.$el.classList.add('timeline-grid-row--dragging')
        this.initialScrollLeft = this.scrollLeft
      }

      const deltaScroll = this.scrollLeft - this.initialScrollLeft
      this.startOffset = deltaX + deltaScroll
      this.endOffset = this.startOffset
    },
    /**
     * Stops the dragging and updates the row by emitting an event that contains the final
     * start and end offset of the row. It's up to the parent to transform these offsets
     * to actual dates.
     */
    up(event) {
      event.preventDefault()
      this.$el.classList.remove('timeline-grid-row--dragging')
      this.$emit('updating-row', false)

      if (this.$el.upEvent) {
        window.removeEventListener('mousemove', this.$el.moveEvent)
        window.removeEventListener('mouseup', this.$el.upEvent)
        this.$el.moveEvent = null
        this.$el.upEvent = null
      }

      if (!this.dragging) {
        this.$emit('edit-row')
        return
      }
      this.dragging = false

      const deltaScroll = this.scrollLeft - this.initialScrollLeft
      const deltaX = event.clientX - this.mouseStart
      this.startOffset = deltaX + deltaScroll
      this.endOffset = this.startOffset

      this.updateRow()
    },
  },
}
</script>

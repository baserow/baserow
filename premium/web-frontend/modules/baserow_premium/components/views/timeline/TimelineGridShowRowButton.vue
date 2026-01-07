<template>
  <div
    v-tooltip="tooltipText"
    :tooltip-position="tooltipPosition"
    @mousedown="onMouseDown"
  >
    <i :class="[icon]"></i>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'

export default {
  name: 'TimelineGridShowRowButton',
  emits: ['mousedown'],
  props: {
    label: {
      type: String,
      required: true,
    },
    date: {
      type: String,
      default: null,
    },
    timezone: {
      type: String,
      required: true,
    },
    tooltipPosition: {
      type: String,
      default: 'bottom-right',
    },
    icon: {
      type: String,
      default: 'iconoir-nav-arrow-left',
    },
  },
  computed: {
    computedDate() {
      return this.getDate(this.date, this.timezone)
    },
    tooltipText() {
      return this.getTooltipText(this.label, this.computedDate)
    },
  },
  methods: {
    getTooltipText(label, date) {
      return `${label} ${date ? `| ${date.format('ll')}` : ''}`
    },
    getDate(dateStr, tzone) {
      return dateStr ? moment(dateStr).tz(tzone) : null
    },
    onMouseDown() {
      this.$emit('mousedown', this.computedDate)
    },
  },
}
</script>

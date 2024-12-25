<template functional>
  <div
    v-tooltip="
      $options.methods.getTooltipText(
        props.label,
        $options.methods.getDate(props.date, props.timezone)
      )
    "
    :class="[data.staticClass, data.class]"
    :tooltip-position="props.tooltipPosition"
    @mousedown="
      listeners['mousedown'](
        $options.methods.getDate(props.date, props.timezone)
      )
    "
  >
    <i :class="[props.icon]"></i>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'

export default {
  name: 'TimelineGridShowRowButton',
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
  methods: {
    getTooltipText(label, date) {
      return `${label} ${date ? `| ${date.format('ll')}` : ''}`
    },
    getDate(dateStr, tzone) {
      return dateStr ? moment(dateStr).tz(tzone) : null
    },
  },
}
</script>

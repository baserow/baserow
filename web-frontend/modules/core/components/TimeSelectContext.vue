<template>
  <Context
    ref="context"
    :hide-on-click-outside="hideOnClickOutside"
    class="time-select"
    max-height-if-outside-viewport
  >
    <ul @mousedown="$event.preventDefault()">
      <li v-for="time in getTimes(notation)" :key="time">
        <a :class="{ active: time === value }" @click="select(time)">
          {{ time }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'TimeSelectContext',
  mixins: [context],
  props: {
    hideOnClickOutside: {
      type: Boolean,
      default: true,
      required: false,
    },
    notation: {
      type: String,
      default: '24',
      required: false,
    },
    value: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['input'],
  methods: {
    /**
     * Generates a list of times that the user can choose from. It ranges from 00:00
     * until 23:30. It adds AM/PM if the notation is in 12 hour format.
     */
    getTimes(notation) {
      const date = moment.utc('1970-01-01 00:00:00')
      const times = []
      const format = notation === '12' ? 'hh:mm A' : 'HH:mm'
      while (date.date() === 1) {
        times.push(date.format(format))
        date.add(30, 'minutes')
      }
      return times
    },
    select(value) {
      this.$emit('input', value)
    },
  },
}
</script>

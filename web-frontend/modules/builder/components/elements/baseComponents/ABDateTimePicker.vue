<template>
  <div ref="wrapper" class="ab-datetime-picker__wrapper">
    <i
      class="button-icon__icon iconoir-calendar"
      @click="$refs.dateContext.show($refs.wrapper, 'bottom', 'left', 0)"
    />
    <ABInput
      v-model="dateInputValue"
      class="ab-datetime-picker__input"
      :placeholder="dateFormat"
      @focus="$refs.dateContext.toggle($refs.wrapper, 'bottom', 'left', 0)"
      @click="$refs.dateContext.show($refs.wrapper, 'bottom', 'left', 0)"
      @blur="
        updateDate($event.target.value)
        $refs.dateContext.hide()
      "
      @input="updateCalendar"
    />
    <div ref="timeWrapper">
      <ABInput
        v-if="includeTime"
        v-model="timeInputValue"
        class="ab-datetime-picker__input"
        :placeholder="timeFormat"
        @focus="$refs.timeContext.toggle($refs.timeWrapper, 'bottom', 'left')"
        @click="$refs.timeContext.show($refs.timeWrapper, 'bottom', 'left')"
        @blur="
          updateTime($event.target.value)
          $refs.timeContext.hide()
        "
      />
    </div>
    <Context
      ref="dateContext"
      :hide-on-click-outside="true"
      :style="calendarStyle"
      class="ab-datetime-picker__calendar--context"
    >
      <client-only>
        <date-picker
          v-model="calendarValue"
          :inline="true"
          :monday-first="true"
          :use-utc="true"
          class="ab-datetime-picker__calendar"
          @input="updateDate"
        />
      </client-only>
    </Context>
    <Context
      ref="timeContext"
      :hide-on-click-outside="true"
      class="ab-datetime-picker__clock"
      :style="clockStyle"
    >
      <client-only>
        <ul @mousedown="$event.preventDefault()">
          <li v-for="time in getTimePickerTimes()" :key="time">
            <a
              :class="{ active: time === timeInputValue }"
              @click="updateTime(time)"
            >
              {{ time }}
            </a>
          </li>
        </ul>
      </client-only>
    </Context>
  </div>
</template>

<script>
import { DATE_FORMATS, TIME_FORMATS } from '@baserow/modules/builder/enums'
import moment from '@baserow/modules/core/moment'
import { FormattedDate, FormattedDateTime } from '@baserow/modules/builder/date'

export default {
  name: 'ABDateTimePicker',
  props: {
    value: {
      type: [FormattedDate, FormattedDateTime],
      required: false,
      default: null,
    },
    dateFormat: {
      type: String,
      required: false,
      default: DATE_FORMATS.ISO.format,
    },
    timeFormat: {
      type: String,
      required: false,
      default: TIME_FORMATS['24'].format,
    },
    includeTime: {
      type: Boolean,
      required: false,
      default: false,
    },
    calendarStyle: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    clockStyle: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
  data() {
    return {
      dateInputValue: '',
      timeInputValue: '',
      calendarValue: null,
    }
  },
  watch: {
    value: {
      handler(value) {
        if (!value) {
          // The input values should be empty when the value is initialized
          // or when the user wipes out the fields
          this.dateInputValue = ''
          this.timeInputValue = ''
          this.calendarValue = null
        } else {
          // If date and/or time are invalid, `toString` will return `Invalid Date`
          this.dateInputValue = value.toString(this.dateFormat)
          this.timeInputValue = this.includeTime
            ? value.toString(this.timeFormat)
            : null
          // It is not possible to display an invalid date in the calendar,
          // so we clean it when the date is invalid
          this.calendarValue = value.isValid() ? value.toDate() : null
        }
      },
      immediate: true,
    },
    dateFormat: {
      handler(value) {
        this.dateInputValue = this.value ? this.value.toString(value) : ''
      },
      immediate: true,
    },
    timeFormat: {
      handler(value) {
        this.timeInputValue = this.value ? this.value.toString(value) : ''
      },
      immediate: true,
    },
  },
  methods: {
    /**
     * Generate a list of times the user can choose from, spaced 30 min apart.
     */
    getTimePickerTimes() {
      const numberOfHalfHoursInADay = 24 * 2
      return Array.from({ length: numberOfHalfHoursInADay }, (_, i) =>
        moment()
          .startOf('day')
          .add(i * 30, 'minutes')
          .format(this.timeFormat)
      )
    },
    /**
     * Update the current input 'value' with the given date.
     * @param {string} value - The string date value.
     */
    updateDate(value) {
      // Clean the input value if there are no values in date and time inputs
      if (!value && !this.timeInputValue) {
        this.$emit('input', null)
        return
      }

      if (this.includeTime) {
        // We start by only including the date format as this is the only part
        // we are updating. If we included the time the date validation would fail,
        // because the date input only contains date values.
        const datetime = new FormattedDateTime(value, this.dateFormat)
        if (this.value && this.value.isValid()) {
          datetime.set('hour', this.value.get('hour'))
          datetime.set('minute', this.value.get('minute'))
        }
        // To keep the time part in future operations we update the format
        // string to also include it
        datetime.format = `${this.dateFormat} ${this.timeFormat}`
        this.$emit('input', datetime)
      } else {
        const date = new FormattedDate(value, this.dateFormat)
        this.$emit('input', date)
      }
    },
    /**
     * Update the current input 'value' with the given time.
     * @param {string} value - The string time value.
     */
    updateTime(value) {
      // Clean the input value if there are no values in date and time inputs
      if (!value && !this.dateInputValue) {
        this.$emit('input', null)
        return
      }

      // Try to parse the time using the chosen format
      let datetime = new FormattedDateTime(value, this.timeFormat)

      // If the parsed time is not valid, we set both hours and minutes to 0
      if (!datetime.isValid()) {
        datetime = new FormattedDateTime('00:00', 'HH:mm')
        datetime.format = this.timeFormat
      }

      // Include the year month and date values from the date input
      if (this.value && this.value.isValid()) {
        datetime.set('year', this.value.get('year'))
        datetime.set('month', this.value.get('month'))
        datetime.set('date', this.value.get('date'))
        // To keep the date part in future operations we update the format
        // string to also include it
        datetime.format = `${this.dateFormat} ${this.timeFormat}`
      }

      this.$emit('input', datetime)
    },
    /**
     * Update the calendar value based on a string date value.
     * @param {string} value - The string date value.
     */
    updateCalendar(value) {
      const date = new FormattedDate(value, this.dateFormat)
      if (date.isValid()) {
        this.calendarValue = date.toDate()
      }
    },
  },
}
</script>

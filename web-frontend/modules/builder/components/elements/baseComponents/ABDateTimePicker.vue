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
      @input="updateCalendar"
      @keydown.enter.prevent="$event.target.blur()"
      @blur="
        updateDate($event.target.value)
        $refs.dateContext.hide()
      "
    />
    <div ref="timeWrapper">
      <ABInput
        v-if="includeTime"
        v-model="timeInputValue"
        class="ab-datetime-picker__input"
        :placeholder="timeFormat"
        @focus="$refs.timeContext.toggle($refs.timeWrapper, 'bottom', 'left')"
        @click="$refs.timeContext.show($refs.timeWrapper, 'bottom', 'left')"
        @keydown.enter.prevent="$event.target.blur()"
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
import {
  generateTimePickerTimes,
  parseDateForCalendar,
  updateDateTime,
} from '@baserow/modules/builder/date'
import { DateOnly } from '@baserow/modules/core/utils/date'
import moment from '@baserow/modules/core/moment'
export default {
  name: 'ABDateTimePicker',
  props: {
    value: {
      type: [String, DateOnly, Date],
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
        this.refreshDate(value)
      },
      immediate: true,
    },
    dateFormat: {
      handler(value) {
        this.refreshDate(this.value)
      },
      immediate: true,
    },
    timeFormat: {
      handler(value) {
        this.refreshDate(this.value)
      },
      immediate: true,
    },
  },
  methods: {
    refreshDate(value) {
      if (!value) {
        // The input values should be empty when the value is initialized
        // or when the user wipes out the fields
        this.dateInputValue = ''
        this.timeInputValue = ''
        this.calendarValue = null
      } else {
        const dateValue = moment(value)

        if (!dateValue.isValid()) {
          // The value is invalid
          // It is not possible to display an invalid date in the calendar,
          // so we clean it when the date is invalid
          this.calendarValue = null
          return
        }

        this.dateInputValue = dateValue.format(this.dateFormat)
        this.timeInputValue = this.includeTime
          ? dateValue.format(this.timeFormat)
          : null

        this.calendarValue = dateValue.toDate()
      }
    },
    /**
     * Generate a list of times the user can choose from, spaced 30 min apart.
     */
    getTimePickerTimes() {
      return generateTimePickerTimes(this.timeFormat)
    },
    /**
     * Update the current input 'value' with the given date.
     * @param {Date|string} value - The date value (JS Date from picker, string from input).
     */
    updateDate(value) {
      // Update the input value even if the final date is invalid
      const date = moment.utc(value, this.dateFormat, true)
      if (date.isValid()) {
        this.dateInputValue = date.format(this.dateFormat)
      }

      this.$emit(
        'input',
        updateDateTime(
          value,
          this.timeInputValue,
          this.includeTime,
          false,
          this.dateFormat,
          this.timeFormat
        )
      )
    },
    /**
     * Update the current input 'value' with the given time.
     * @param {string} value - The string time value.
     */
    updateTime(value) {
      // Update the input value even if the final date is invalid
      const date = moment.utc(value, this.timeFormat, true)
      if (date.isValid()) {
        this.timeInputValue = date.format(this.timeFormat)
      }

      this.timeInputValue = value
      this.$emit(
        'input',
        updateDateTime(
          this.dateInputValue,
          value,
          this.includeTime,
          true,
          this.dateFormat,
          this.timeFormat
        )
      )

      this.$refs.timeContext.hide()
    },
    /**
     * Update the calendar value based on a string date value.
     * @param {string} value - The string date value.
     */
    updateCalendar(value) {
      this.calendarValue = parseDateForCalendar(value, this.dateFormat)
    },
  },
}
</script>

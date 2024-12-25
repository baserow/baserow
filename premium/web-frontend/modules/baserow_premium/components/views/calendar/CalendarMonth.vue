<template>
  <div class="calendar-month-wrapper">
    <div v-if="timezoneAndDateLoaded(fields)" class="calendar-month">
      <div class="calendar-month__header">
        <ViewDateIndicator
          :date="selectedDate(fields)"
          class="calendar-month__header-selected-month"
        />
        <ViewDateSelector
          :selected-date="selectedDate(fields)"
          unit="month"
          @date-selected="selectDate"
        />
      </div>
      <ol class="calendar-month__days-grid">
        <li v-if="showMonthOnlyLoadingOverlay" class="loading-overlay"></li>
        <li
          v-for="weekDay in weekDays"
          :key="weekDay"
          class="calendar-month-day__week-day"
        >
          {{ weekDay }}
        </li>
        <CalendarMonthDay
          v-for="day in days"
          :key="day.dateString"
          :day="day"
          :fields="fields"
          :store-prefix="storePrefix"
          :database="database"
          :read-only="readOnly"
          :table="table"
          :view="view"
          v-on="$listeners"
        >
        </CalendarMonthDay>
      </ol>
    </div>
    <div v-else class="loading-overlay"></div>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import ViewDateIndicator from '@baserow_premium/components/views/ViewDateIndicator'
import ViewDateSelector from '@baserow_premium/components/views/ViewDateSelector'
import CalendarMonthDay from '@baserow_premium/components/views/calendar/CalendarMonthDay'
import {
  getMonthlyTimestamps,
  getDateInTimezone,
  weekDaysShort,
} from '@baserow/modules/core/utils/date'
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import debounce from 'lodash/debounce'

export default {
  name: 'CalendarMonth',
  components: {
    ViewDateIndicator,
    ViewDateSelector,
    CalendarMonthDay,
  },
  props: {
    fields: {
      type: Array,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
    loading: {
      type: Boolean,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: false,
      default: undefined,
    },
  },
  data() {
    return {
      today: moment.tz(this.timezone).format('YYYY-MM-DD'),
      selectDateDebounced: null,
    }
  },
  computed: {
    showMonthOnlyLoadingOverlay() {
      return !this.loading && this.rowsLoading
    },
    monthlyTimestamps() {
      return getMonthlyTimestamps(this.selectedDate(this.fields))
    },
    numberOfDaysInMonth() {
      return moment(this.selectedDate(this.fields)).daysInMonth()
    },
    currentMonthDays() {
      return [...Array(this.numberOfDaysInMonth)].map((day, index) => {
        const date = getDateInTimezone({
          year: this.selectedDate(this.fields).year(),
          month: this.selectedDate(this.fields).month(),
          day: index + 1,
          timezone: this.selectedDate(this.fields).tz(),
        })
        const dateString = date.format('YYYY-MM-DD')
        return {
          date,
          dateString,
          isCurrentMonth: true,
          isWeekend: this.isWeekend(date),
          isToday: dateString === this.today,
        }
      })
    },
    previousMonthDays() {
      const {
        visibleNumberOfDaysFromPreviousMonth,
        firstMondayDayOfRange,
        firstDayPreviousMonth,
      } = this.monthlyTimestamps
      return [...Array(visibleNumberOfDaysFromPreviousMonth)].map(
        (day, index) => {
          const date = getDateInTimezone({
            year: firstDayPreviousMonth.year(),
            month: firstDayPreviousMonth.month(),
            day: firstMondayDayOfRange + index,
            timezone: this.selectedDate(this.fields).tz(),
          })
          const dateString = date.format('YYYY-MM-DD')
          return {
            date,
            dateString,
            isCurrentMonth: false,
            isWeekend: this.isWeekend(date),
            isToday: dateString === this.today,
          }
        }
      )
    },
    nextMonthDays() {
      const { visibleNumberOfDaysFromNextMonth, firstDayNextMonth } =
        this.monthlyTimestamps
      return [...Array(visibleNumberOfDaysFromNextMonth)].map((day, index) => {
        const date = getDateInTimezone({
          year: firstDayNextMonth.year(),
          month: firstDayNextMonth.month(),
          day: index + 1,
          timezone: this.selectedDate(this.fields).tz(),
        })
        const dateString = date.format('YYYY-MM-DD')
        return {
          date,
          dateString,
          isCurrentMonth: false,
          isWeekend: this.isWeekend(date),
          isToday: dateString === this.today,
        }
      })
    },
    days() {
      return [
        ...this.previousMonthDays,
        ...this.currentMonthDays,
        ...this.nextMonthDays,
      ]
    },
    weekDays() {
      return weekDaysShort()
    },
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        timezoneAndDateLoaded:
          this.$options.propsData.storePrefix +
          'view/calendar/getCalendarTimezoneAndDateLoaded',
        rowsLoading:
          this.$options.propsData.storePrefix + 'view/calendar/getLoadingRows',
        timezone:
          this.$options.propsData.storePrefix + 'view/calendar/getTimeZone',
        selectedDate:
          this.$options.propsData.storePrefix + 'view/calendar/getSelectedDate',
      }),
    }
  },
  async mounted() {
    this.today = moment.tz(this.timezone(this.fields)).format('YYYY-MM-DD')
    if (!this.timezoneAndDateLoaded(this.fields)) {
      // The server side load didn't happen as it couldn't figure out the timezone,
      // lets do it client side where we can guess the users timezone safely.
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/calendar/fetchInitial',
          {
            fields: this.fields,
          }
        )
      } catch (error) {
        notifyIf(error)
      }
    }
  },
  methods: {
    selectDate(newSelectedDate) {
      // Set loading immediately so the overlay appears without waiting for the
      // debounce delay.
      this.$store.dispatch(
        this.storePrefix + 'view/calendar/selectDateAndStartLoading',
        {
          selectedDate: newSelectedDate,
        }
      )
      if (this.selectDateDebounced) {
        this.selectDateDebounced.cancel()
      }

      this.selectDateDebounced = debounce(this.selectDateImmediately, 400)
      this.selectDateDebounced(newSelectedDate)
    },
    async selectDateImmediately(newSelectedDate) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/calendar/fetchMonthly',
          {
            dateTime: newSelectedDate,
            fields: this.fields,
          }
        )
      } catch (error) {
        notifyIf(error)
      }
    },
    isWeekend(date) {
      const dayOfWeek = moment(date).isoWeekday()
      return dayOfWeek === 6 || dayOfWeek === 7
    },
  },
}
</script>

import moment from '@baserow/modules/core/moment'
import {
  getCellTimezoneAbbr,
  getDateHumanReadableFormat,
  getDateMomentFormat,
  getFieldTimezone,
  getTimeHumanReadableFormat,
  getTimeMomentFormat,
} from '@baserow/modules/database/utils/date'

const DATE_PICKER_FORMAT = 'YYYY-MM-DD'

/**
 * Mixin that introduces methods for the date field. This can both be used for a row
 * and grid view field.
 */
export default {
  data() {
    return {
      date: '',
      pickerDate: '',
      time: '',
      momentDate: null,
    }
  },
  computed: {
    /**
     * We need to watch the value and the date/time formats. This can easily be done
     * with a computed property.
     */
    valueAndFormats() {
      return `${this.value}|${this.field.date_format}|${this.field.date_time_format}|${this.field.date_force_timezone}`
    },
    fieldDateFormat() {
      return getDateMomentFormat(this.field.date_format)
    },
  },
  watch: {
    /**
     * When the value or one of the date formats changes we need to update the date
     * and time data with the correct values. This is because the date and time data
     * are directly visible to the user and not the value like most other fields.
     */
    valueAndFormats() {
      if (!this.editing) {
        this.setDateAndTime(this.field, this.value)
      }
    },
  },
  created() {
    this.setDateAndTime(this.field, this.value)
  },
  methods: {
    updateFormattedDateValue() {
      const pickerDate = this.momentDate.clone()

      // Because of some bugs with parsing and localizing correctly dates in the
      // vuejs3-datepicker component passed both as string and dates, we need to
      // localize the date correctly and replace the timezone with the browser
      // timezone. This is needed to be able to show the correct date in the
      // datepicker.
      const timezone = getFieldTimezone(this.field)
      if (timezone !== null) {
        pickerDate.tz(timezone)
      }
      pickerDate.tz(moment.tz.guess(), true)

      this.pickerDate = pickerDate.toDate()
      this.date = this.momentDate.format(this.fieldDateFormat)
    },
    updateFormattedTimeValue() {
      const timeFormat = getTimeMomentFormat(this.field.date_time_format)
      this.time = this.momentDate.format(timeFormat)
    },
    /**
     * When the date part is updated we also need to update the copy data which
     * contains the whole date(time) in the correct format. The copy contains the
     * value that is actually going to be saved.
     */
    updateDate(field, value) {
      const dateFormats = [DATE_PICKER_FORMAT, this.fieldDateFormat]
      const newDate = moment.utc(value, dateFormats, true)
      const timezone = getFieldTimezone(field)
      // default to now if no time is set
      const now = moment.utc()

      if (timezone !== null) {
        newDate.tz(timezone, true)
        now.tz(timezone)
      }

      if (newDate.isValid()) {
        const momentDate = this.momentDate || now
        newDate.set({
          hour: momentDate.hour(),
          minute: momentDate.minute(),
          second: momentDate.second(),
        })

        // needed again to be able to format correctly the moment date
        // composed by the date and time parts separately
        if (timezone !== null) {
          newDate.tz(timezone)
        }

        this.updateCopy(field, newDate)
        this.updateFormattedDateValue()
      } else {
        this.updateCopy(field, null)
      }
    },
    /**
     * When the time part is updated we also need to update the copy data which
     * contains the whole date(time) in the correct format. The copy contains the
     * value that is actually going to be saved.
     */
    updateTime(field, value) {
      const newTime = moment.utc(value, ['hh:mm a', 'HH:mm'], true)

      const timezone = getFieldTimezone(field)
      if (timezone !== null) {
        newTime.tz(timezone, true)
      }

      if (newTime.isValid()) {
        if (this.momentDate !== null) {
          newTime.set({
            year: this.momentDate.year(),
            month: this.momentDate.month(),
            date: this.momentDate.date(),
          })

          // needed again to be able to format correctly the moment date
          // composed by the date and time parts separately
          if (timezone !== null) {
            newTime.tz(timezone)
          }
        }

        this.updateCopy(field, newTime)
        this.updateFormattedTimeValue()
      } else {
        this.time = value
      }
    },
    /**
     * When the user uses the datepicker to choose a date, we also need to update
     * date data and the copy so that the correct date is visible for the user.
     */
    chooseDate(field, value) {
      const timezone = getFieldTimezone(field) || 'UTC'
      const momentDate = this.momentDate || moment.utc()
      const pickerDate = moment(value)
        .set({
          hour: momentDate.hour(),
          minute: momentDate.minute(),
          second: momentDate.second(),
        })
        .tz(timezone, true)
      this.updateCopy(field, pickerDate)
      this.updateFormattedDateValue()
    },
    /**
     * When the user uses the time context to choose a time, we also need to update
     * time data and the copy so that the correct time is visible for the user.
     */
    chooseTime(field, value) {
      this.updateTime(field, value)
      this.time = value
    },
    /**
     * A helper method that allows updating the copy data by only changing certain
     * properties of a datetime. For example only the month could be updated.
     */
    updateCopy(field, newMomentDate) {
      if (newMomentDate === null) {
        this.copy = null
        this.momentDate = null
      } else {
        this.momentDate = newMomentDate
        this.copy = field.date_include_time
          ? this.momentDate.format()
          : this.momentDate.format('YYYY-MM-DD')
      }
    },
    /**
     * Updates the date and time data by converting the value to the correct formats.
     */
    setDateAndTime(field, value) {
      if (value === null) {
        this.momentDate = null
        this.date = this.time = this.pickerDate = ''
      } else {
        const timezone = getFieldTimezone(field)
        this.momentDate = moment.utc(value, moment.ISO_8601, true)

        if (timezone) {
          this.momentDate.tz(timezone)
        }

        this.updateFormattedDateValue()
        this.updateFormattedTimeValue()
      }
    },
    getCellTimezoneAbbr(field, value, force) {
      return getCellTimezoneAbbr(field, value, { force })
    },
    /**
     * Returns a human readable date placeholder of the format for the input.
     */
    getDatePlaceholder(field) {
      return this.$t(
        'humanDateFormat.' + getDateHumanReadableFormat(field.date_format)
      )
    },
    /**
     * Returns a human readable time placeholder of the format for the input.
     */
    getTimePlaceholder(field) {
      return getTimeHumanReadableFormat(field.date_time_format)
    },
    /**
     * When the user focuses on one of the inputs the related context menu must
     * also be opened.
     */
    focus(context, event) {
      context.toggle(event.currentTarget, 'bottom', 'left', 0)
    },
    /**
     * When the user blurs one of the inputs the related context menu must also be
     * hidden.
     */
    blur(context, event) {
      // The ?. prevents an exception when the context was removed from the DOM then
      // the blur event is triggered
      context?.hide()
    },
  },
}

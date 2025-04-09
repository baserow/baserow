import {
  getDateMomentFormat,
  getTimeMomentFormat,
  getCellTimezoneAbbr,
  getFieldTimezone,
} from '@baserow/modules/database/utils/date'
import moment from '@baserow/modules/core/moment'

export default {
  methods: {
    getDate(field, value) {
      if (value === null || value === undefined) {
        return ''
      }

      const timezone = getFieldTimezone(field)
      const existing = moment.utc(value, moment.ISO_8601, true)
      if (timezone) {
        existing.tz(timezone)
      }

      const dateFormat = getDateMomentFormat(field.date_format)
      return existing.format(dateFormat)
    },
    getTime(field, value) {
      if (value === null || value === undefined) {
        return ''
      }

      const timezone = getFieldTimezone(field)
      const existing = moment.utc(value, moment.ISO_8601, true)
      if (timezone) {
        existing.tz(timezone)
      }

      const timeFormat = getTimeMomentFormat(field.date_time_format)
      return existing.format(timeFormat)
    },
    getCellTimezoneAbbr(field, value) {
      return getCellTimezoneAbbr(field, value)
    },
  },
}

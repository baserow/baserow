import moment from '@baserow/modules/core/moment'
import {
  splitTimezoneAndFilterValue,
  DATE_FILTER_VALUE_SEPARATOR,
} from '@baserow/modules/database/utils/date'
import filterTypeInput from '@baserow/modules/database/mixins/filterTypeInput'

export default {
  mixins: [filterTypeInput],
  setup: filterTypeInput.setup,
  data() {
    return {
      copy: '',
      timezoneValue: null,
    }
  },
  watch: {
    'filter.value'(value) {
      this.setCopy(value)
    },
  },
  created() {
    this.setCopy(this.filter.value)
  },
  methods: {
    getSeparator() {
      return DATE_FILTER_VALUE_SEPARATOR
    },
    getDefaultTimezone() {
      return this.field.date_force_timezone || moment.tz.guess()
    },
    getTimezone() {
      if (this.timezoneValue === null || this.timezoneValue === undefined) {
        this.timezoneValue = this.getDefaultTimezone()
      }
      return this.timezoneValue
    },
    getTimezoneAbbr() {
      const timezone = this.getTimezone()
      return timezone !== undefined ? moment.utc().tz(timezone).format('z') : ''
    },
    splitCombinedValue(value) {
      const [timezone, filterValue] = splitTimezoneAndFilterValue(value)
      return [timezone, filterValue]
    },
    setCopy(value) {
      const [timezone, filterValue] = this.splitCombinedValue(value)
      this.copy = filterValue
      this.timezoneValue = timezone
    },
    prepareValue(value, field) {
      const sep = this.getSeparator()
      const timezone = this.getTimezone()
      return timezone ? `${timezone}${sep}${value}` : value
    },
    delayedUpdate(value, immediately = false) {
      const combinedValue = this.prepareValue(value, this.field)
      return this.$super(filterTypeInput).delayedUpdate(
        combinedValue,
        immediately
      )
    },
  },
}

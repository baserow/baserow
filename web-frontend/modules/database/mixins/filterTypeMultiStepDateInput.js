import moment from '@baserow/modules/core/moment'
import {
  splitMultiStepDateValue,
  DATE_FILTER_VALUE_SEPARATOR,
} from '@baserow/modules/database/utils/date'
import filterTypeInput from '@baserow/modules/database/mixins/filterTypeInput'

export default {
  mixins: [filterTypeInput],
  setup: filterTypeInput.setup,
  data() {
    return {
      copy: '',
      timezoneValue: '',
      operatorValue: '',
    }
  },
  watch: {
    'filter.value': {
      handler(value) {
        this.setCopy(value)
      },
      immediate: true,
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
      if (!this.timezoneValue) {
        this.timezoneValue = this.getDefaultTimezone()
      }
      return this.timezoneValue
    },
    getTimezoneAbbr() {
      const timezone = this.getTimezone()
      return timezone ? moment.utc().tz(timezone).format('z') : ''
    },
    splitCombinedValue(value) {
      const [timezone, filterValue, operatorValue] =
        splitMultiStepDateValue(value)
      return [timezone, filterValue, operatorValue]
    },
    prepareValue(value, field) {
      const sep = this.getSeparator()
      const timezone = this.getTimezone()
      const valueAndOperator = `${value}${sep}${this.operatorValue}`
      return timezone
        ? `${timezone}${sep}${valueAndOperator}`
        : valueAndOperator
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

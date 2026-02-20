<template>
  <div class="filters__value-date-timezone">
    <div ref="date">
      <FormInput
        v-model="dateString"
        :disabled="disabled"
        :error="v$.dateString.$error"
        :placeholder="getDatePlaceholder(field)"
        @focus="$refs.dateContext.toggle($refs.date, 'bottom', 'left', 0)"
        @blur="$refs.dateContext.hide()"
        @input="setCopyFromDateString($event, 'dateString')"
        @keydown.enter="delayedUpdate(copy, true)"
      >
      </FormInput>
      <Context
        ref="dateContext"
        :hide-on-click-outside="false"
        class="datepicker-context"
      >
        <client-only>
          <date-picker
            :inline="true"
            :monday-first="true"
            :use-utc="true"
            :model-value="dateObject"
            :language="datePickerLanguage"
            :open-date="dateObject || new Date()"
            class="datepicker"
            @update:model-value="chooseDate($event)"
          ></date-picker>
        </client-only>
      </Context>
    </div>
    <div class="filters__value-timezone">{{ getTimezoneAbbr() }}</div>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import moment from '@baserow/modules/core/moment'
import {
  getDateMomentFormat,
  getDateHumanReadableFormat,
} from '@baserow/modules/database/utils/date'
import filterTypeDateInput from '@baserow/modules/database/mixins/filterTypeDateInput'
import { useDatePickerLanguage } from '@baserow/modules/core/composables/useDatePickerLanguage'

export default {
  name: 'ViewFilterTypeDate',
  mixins: [filterTypeDateInput],
  setup() {
    return { v$: useVuelidate({ $lazy: true }), ...useDatePickerLanguage() }
  },
  data() {
    return {
      dateString: '',
      dateObject: null,
    }
  },
  mounted() {
    this.nextTick(() => {
      this.v$.$touch()
    })
  },
  methods: {
    isInputValid() {
      return !this.v$.dateString.$error
    },
    chooseDate(value) {
      const timezone = this.getTimezone()
      const pickerDate = moment(value)
      if (!pickerDate.isValid()) {
        return
      } else if (timezone !== null) {
        pickerDate.tz(timezone, true)
      }

      this.setCopy(pickerDate.format('YYYY-MM-DD'), 'dateObject')
      this.delayedUpdate(this.copy, true)
    },
    setDateObject(date) {
      // Because of some bugs with parsing and localizing correctly dates
      // in the vuejs3-datepicker component passed both as string and
      // dates, we need to localize the date correctly and replace the
      // timezone with the browser timezone. This is needed to be able to
      // show the correct date in the datepicker.

      if (date === null) {
        this.dateObject = null
        return
      }

      const pickerDate = date.clone()
      pickerDate.tz(moment.tz.guess(), true)
      this.dateObject = pickerDate.toDate()
    },
    setCopy(value, sender) {
      const [timezone, filterValue] = this.splitCombinedValue(value)
      this.timezoneValue = timezone
      const newDate = moment.utc(
        filterValue,
        ['YYYY-MM-DD', getDateMomentFormat(this.field.date_format)],
        true
      )
      if (timezone !== null) {
        newDate.tz(timezone, true)
      }

      if (newDate.isValid()) {
        this.copy = newDate.format('YYYY-MM-DD')

        if (sender !== 'dateObject') {
          this.setDateObject(newDate)
        }

        if (sender !== 'dateString') {
          const dateFormat = getDateMomentFormat(this.field.date_format)
          this.dateString = newDate.format(dateFormat)
        }
      }
    },
    setCopyFromDateString(value, sender) {
      if (value === '') {
        this.copy = ''
        return
      }

      const dateFormat = getDateMomentFormat(this.field.date_format)
      const timezone = this.getTimezone()
      const newDate = moment(value, dateFormat, true)
      if (timezone !== null) {
        newDate.tz(timezone, true)
      }

      if (newDate.isValid()) {
        this.setCopy(newDate.format('YYYY-MM-DD'), sender)
        this.delayedUpdate(this.copy, true)
      } else {
        this.copy = value
      }
    },
    getDatePlaceholder(field) {
      return this.$t(
        'humanDateFormat.' + getDateHumanReadableFormat(field.date_format)
      )
    },
    focus() {
      this.$refs.date.focus()
    },
  },
  validations() {
    return {
      copy: {},
      dateString: {
        isValidDate(value) {
          const dateFormat = getDateMomentFormat(this.field.date_format)
          return value === '' || moment(value, dateFormat, true).isValid()
        },
      },
    }
  },
}
</script>

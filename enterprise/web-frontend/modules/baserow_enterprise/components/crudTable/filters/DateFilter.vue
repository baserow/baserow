<template>
  <div>
    <div ref="date">
      <FormInput
        v-model="dateString"
        :error="v$.copy?.$error"
        :disabled="disabled"
        :placeholder="placeholder"
        @focus="$refs.dateContext.toggle($refs.date, 'bottom', 'left', 0)"
        @click="$refs.dateContext.show($refs.date, 'bottom', 'left', 0)"
        @blur="$refs.dateContext.hide()"
        @input="
          ;[
            setCopyFromDateString(dateString, 'dateString'),
            $emit('input', copy),
          ]
        "
        @keydown.enter="$emit('input', copy)"
      ></FormInput>
    </div>
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
          :disabled-dates="disableDates"
          class="datepicker"
          @update:model-value="
            ;[
              setCopy($event, 'dateObject'),
              $emit('input', copy),
              $refs.dateContext.hide(),
            ]
          "
        ></date-picker>
      </client-only>
    </Context>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import moment from '@baserow/modules/core/moment'
import {
  getDateMomentFormat,
  getDateHumanReadableFormat,
} from '@baserow/modules/database/utils/date'
import { useDatePickerLanguage } from '@baserow/modules/core/composables/useDatePickerLanguage'

export default {
  name: 'DateFilter',
  emits: ['input'],
  props: {
    value: {
      type: String,
      default: null,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    placeholder: {
      type: String,
      default: '',
    },
    disableDates: {
      type: Object,
      default: () => ({}),
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }), ...useDatePickerLanguage() }
  },
  data() {
    return {
      copy: '',
      dateString: '',
      dateObject: '',
      datePickerLang: {
        en: {},
        fr: {},
      },
    }
  },
  created() {
    this.setCopy(this.value)
  },
  mounted() {
    this.v$.$touch()
  },
  methods: {
    clear() {
      this.copy = ''
      this.dateString = ''
      this.$emit('input', null)
    },
    setCopy(value, sender) {
      if (value === null) {
        this.copy = ''
        return
      }

      const newDate = moment(value)

      if (newDate.isValid()) {
        this.copy = newDate.format('YYYY-MM-DD')

        if (sender !== 'dateObject') {
          // Because of some bugs with parsing and localizing correctly dates in
          // the vuejs3-datepicker component passed both as string and dates, we
          // need to localize the date correctly and replace the timezone with
          // the browser timezone. This is needed to be able to show the correct
          // date in the datepicker.
          const newPickerDate = newDate.clone()
          newPickerDate.tz(moment.tz.guess(), true)

          this.dateObject = newPickerDate.toDate()
        }

        if (sender !== 'dateString') {
          const dateFormat = getDateMomentFormat('US')
          this.dateString = newDate.format(dateFormat)
        }
      }
    },
    setCopyFromDateString(value, sender) {
      if (value === '') {
        this.copy = ''
        return
      }

      const dateFormat = getDateMomentFormat('US')
      const newDate = moment.utc(value, dateFormat)

      if (newDate.isValid()) {
        this.setCopy(newDate, sender)
      } else {
        this.copy = value
      }
    },
    getDatePlaceholder(field) {
      return this.$t('humanDateFormat.' + getDateHumanReadableFormat('US'))
    },
    focus() {
      this.$refs.date.focus()
    },
  },
  validations() {
    return {
      copy: {
        date(value) {
          return value === '' || moment(value).isValid()
        },
      },
    }
  },
}
</script>

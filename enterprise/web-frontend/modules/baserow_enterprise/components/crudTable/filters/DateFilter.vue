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
          :value="dateObject"
          :language="datePickerLang[$i18n.locale]"
          :disabled-dates="disableDates"
          class="datepicker"
          @input="
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
import { en, fr } from 'vuejs-datepicker/dist/locale'

export default {
  name: 'DateFilter',
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
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      copy: '',
      dateString: '',
      dateObject: '',
      datePickerLang: {
        en,
        fr,
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

      const newDate = moment.utc(value)

      if (newDate.isValid()) {
        this.copy = newDate.format('YYYY-MM-DD')

        if (sender !== 'dateObject') {
          this.dateObject = newDate.toDate()
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

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
            $emit('input', v$.copy.$model),
          ]
        "
        @keydown.enter="$emit('input', v$.copy.$model)"
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
              $emit('input', v$.copy.$model),
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
import { reactive, computed } from 'vue'
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
      default: () => {},
    },
  },
  data() {
    return {
      dateString: '',
      dateObject: '',
      datePickerLang: {
        en,
        fr,
      },
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      copy: '',
    })

    const rules = computed(() => ({
      copy: {
        date(value) {
          return value === '' || moment(value).isValid()
        },
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values

    this.setCopy(this.value)
  },
  mounted() {
    this.v$.$touch()
  },
  methods: {
    clear() {
      this.values.copy = ''
      this.dateString = ''
      this.$emit('input', null)
    },
    setCopy(value, sender) {
      if (value === null) {
        this.values.copy = ''
        return
      }

      const newDate = moment.utc(value)

      if (newDate.isValid()) {
        this.values.copy = newDate.format('YYYY-MM-DD')

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
        this.values.copy = ''
        return
      }

      const dateFormat = getDateMomentFormat('US')
      const newDate = moment.utc(value, dateFormat)

      if (newDate.isValid()) {
        this.setCopy(newDate, sender)
      } else {
        this.values.copy = value
      }
    },
    getDatePlaceholder(field) {
      return this.$t('humanDateFormat.' + getDateHumanReadableFormat('US'))
    },
    focus() {
      this.$refs.date.focus()
    },
  },
}
</script>

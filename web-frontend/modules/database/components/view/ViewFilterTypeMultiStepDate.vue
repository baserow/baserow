<template>
  <div class="filters__multi-value">
    <Dropdown
      class="filters__multi-value-operator"
      :disabled="disabled"
      :value="operatorValue"
      :fixed-items="true"
      @input="setOperator($event)"
    >
      <template #selectedValue>
        <span
          class="dropdown__selected-text"
          :title="$t(selectedOperatorLabel)"
          >{{ $t(selectedOperatorLabel) }}</span
        >
      </template>
      <DropdownItem
        v-for="opr in filterType.getCompatibleOperators()"
        :key="opr.value"
        :name="opr.stringKey"
        :value="opr.value"
      >
        {{ operatorLabel(opr) }}
      </DropdownItem>
    </Dropdown>

    <FormInput
      v-if="selectedOperator?.hasNrInputValue"
      ref="input"
      v-model="copy"
      class="filters__combined-value-input filters__value-input--small"
      :disabled="disabled"
      @input="setValue($event)"
      @keydown.enter="setValue($event)"
      @keypress="acceptOnlyNumber($event)"
    />

    <div>
      <span ref="date">
        <FormInput
          v-if="selectedOperator?.hasDateInputValue"
          v-model="dateString"
          type="text"
          class="filters__value-input input--small"
          :error="!isInputValid()"
          :disabled="disabled"
          :placeholder="getDatePlaceholder(field)"
          @focus="$refs.dateContext.toggle($refs.date, 'bottom', 'left', 0)"
          @blur="$refs.dateContext.hide()"
          @input="setCopyFromDateString(dateString, 'dateString')"
          @keydown.enter="delayedUpdate(copy, true)"
        />
      </span>

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
            class="datepicker"
            @input="chooseDate($event)"
          ></date-picker>
        </client-only>
      </Context>
    </div>
    <span class="filters__value-timezone">{{ getTimezoneAbbr() }}</span>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import {
  getDateMomentFormat,
  getDateHumanReadableFormat,
} from '@baserow/modules/database/utils/date'
import { en, fr } from 'vuejs-datepicker/dist/locale'
import filterTypeMultiStepDateInput from '@baserow/modules/database/mixins/filterTypeMultiStepDateInput'

export default {
  name: 'ViewFilterTypeMultiStepDate',
  mixins: [filterTypeMultiStepDateInput],
  data() {
    return {
      value: '',
      daysAgoValue: '',
      dateString: '',
      dateObject: '',
      datePickerLang: {
        en,
        fr,
      },
    }
  },
  computed: {
    selectedOperator() {
      return this.filterType
        .getCompatibleOperators()
        .find((opr) => opr.value === this.operatorValue)
    },
    selectedOperatorLabel() {
      const currOpr = this.selectedOperator
      return currOpr ? this.operatorLabel(currOpr) : ''
    },
  },
  methods: {
    isInputValid() {
      return true
    },
    operatorLabel(operator) {
      return this.$t(`${operator.stringKey}`)
    },
    setCopy(combinedValue, sender) {
      const [timezone, value, operator] = this.splitCombinedValue(combinedValue)
      this.operatorValue = operator
      this.timezoneValue = timezone

      if (this.selectedOperator?.hasDateInputValue) {
        const newDate = moment.utc(
          value,
          ['YYYY-MM-DD', getDateMomentFormat(this.field.date_format)],
          true
        )
        if (timezone !== null) {
          newDate.tz(timezone, true)
        }

        if (newDate.isValid()) {
          this.copy = newDate.format('YYYY-MM-DD')

          if (sender !== 'dateObject') {
            this.dateObject = newDate.format('YYYY-MM-DD')
          }

          if (sender !== 'dateString') {
            const dateFormat = getDateMomentFormat(this.field.date_format)
            this.dateString = newDate.format(dateFormat)
          }
        }
      } else {
        this.copy = value
      }
    },
    setOperator(operator) {
      this.operatorValue = operator
      this.delayedUpdate(this.value, true)
    },
    setValue(value) {
      this.copy = value
      this.delayedUpdate(value, true)
    },
    chooseDate(value) {
      const timezone = this.getTimezone()
      const pickerDate = moment.utc(value)
      if (!pickerDate.isValid()) {
        return
      } else if (timezone !== null) {
        pickerDate.tz(timezone, true)
      }

      this.setValue(pickerDate.format('YYYY-MM-DD'), 'dateObject')
    },
    setCopyFromDateString(value, sender) {
      if (value === '') {
        this.copy = ''
        return
      }

      const dateFormat = getDateMomentFormat(this.field.date_format)
      const timezone = this.getTimezone()
      const newDate = moment.utc(value, dateFormat, true)
      if (timezone !== null) {
        newDate.tz(timezone)
      }

      if (newDate.isValid()) {
        const dateString = newDate.format('YYYY-MM-DD')
        this.setValue(dateString, sender)
      } else {
        this.copy = value
      }
    },
    getDatePlaceholder(field) {
      return this.$t(
        'humanDateFormat.' + getDateHumanReadableFormat(field.date_format)
      )
    },
    acceptOnlyNumber($event) {
      const keyCode = $event.keyCode ? $event.keyCode : $event.which
      if ((keyCode < 48 || keyCode > 57) && keyCode !== 46) {
        // 48-57 are 0-9 keys and 46 is the dot
        $event.preventDefault()
      }
    },
    focus() {
      if (this.$refs.date) {
        this.$refs.date.focus()
      }
    },
  },
}
</script>

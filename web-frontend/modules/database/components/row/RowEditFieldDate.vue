<template>
  <div class="field-date__container">
    <FormGroup class="field-date" :error="touched && !valid">
      <FormInput
        ref="date"
        v-model="date"
        size="large"
        :error="touched && !valid"
        :placeholder="getDatePlaceholder(field)"
        :disabled="readOnly"
        icon-right="iconoir-calendar"
        @keyup.enter="$refs.date.blur()"
        @keyup="updateDate(field, date)"
        @focus="focus($refs.dateContext, $event)"
        @blur="blur($refs.dateContext, $event)"
      />

      <Context
        ref="dateContext"
        :hide-on-click-outside="false"
        class="datepicker-context"
      >
        <client-only>
          <date-picker
            v-if="!readOnly"
            :inline="true"
            :monday-first="true"
            :use-utc="true"
            :model-value="pickerDate"
            :language="datePickerLanguage"
            :open-date="pickerDate || new Date()"
            class="datepicker"
            @update:model-value="chooseDate(field, $event)"
          />
        </client-only>
      </Context>
    </FormGroup>

    <FormGroup
      v-if="field.date_include_time"
      :error="touched && !valid"
      class="field-date__time"
    >
      <FormInput
        ref="time"
        v-model="time"
        size="large"
        :error="touched && !valid"
        :placeholder="getTimePlaceholder(field)"
        :disabled="readOnly"
        icon-right="iconoir-clock"
        @keyup.enter="$refs.time.blur()"
        @keyup="updateTime(field, time)"
        @focus="focus($refs.timeContext, $event)"
        @blur="blur($refs.timeContext, $event)"
      />

      <TimeSelectContext
        v-if="!readOnly"
        ref="timeContext"
        :value="time"
        :hide-on-click-outside="false"
        :notation="field.date_time_format"
        @input="chooseTime(field, $event)"
      />

      <template #error>
        <span v-show="touched && !valid">
          {{ error }}
        </span>
      </template>
    </FormGroup>

    <div class="field-date__tzinfo">
      {{ getCellTimezoneAbbr(field, value, { force: true }) }}
    </div>
  </div>
</template>
<script>
import TimeSelectContext from '@baserow/modules/core/components/TimeSelectContext'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import rowEditFieldInput from '@baserow/modules/database/mixins/rowEditFieldInput'
import dateField from '@baserow/modules/database/mixins/dateField'
import { useDatePickerLanguage } from '@baserow/modules/core/composables/useDatePickerLanguage'

export default {
  components: { TimeSelectContext },
  mixins: [rowEditField, rowEditFieldInput, dateField],
  setup() {
    return useDatePickerLanguage()
  },
  methods: {
    focus(...args) {
      this.select()
      dateField.methods.focus.call(this, ...args)
    },
    blur(...args) {
      dateField.methods.blur.call(this, ...args)
      this.unselect()
    },
  },
}
</script>

<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('interval')"
      :label="$t('dataSyncPeriodicIntervalForm.intervalLabel')"
      :helper-text="$t('dataSyncPeriodicIntervalForm.intervalHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="v$.values.interval.$model"
        :disabled="disabled"
        size="large"
      >
        <DropdownItem
          :name="$t('dataSyncPeriodicIntervalForm.manual')"
          value="MANUAL"
        ></DropdownItem>
        <DropdownItem
          :name="$t('dataSyncPeriodicIntervalForm.daily')"
          value="DAILY"
        ></DropdownItem>
        <DropdownItem
          :name="$t('dataSyncPeriodicIntervalForm.hourly')"
          value="HOURLY"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>
    <template v-if="values.interval !== 'MANUAL'">
      <div class="flex align-items-end">
        <FormGroup
          v-if="values.interval === 'DAILY'"
          small-label
          :label="$t('dataSyncPeriodicIntervalForm.hour')"
          :error="v$.hour.$error"
          required
        >
          <FormInput
            v-model="v$.hour.$model"
            :disabled="disabled"
            size="large"
            type="number"
            :min="0"
            :max="23"
            @blur="v$.hour.$touch"
            @input="updateWhen"
          />
        </FormGroup>
        <FormGroup
          small-label
          :label="$t('dataSyncPeriodicIntervalForm.minute')"
          :error="v$.minute.$error"
          required
        >
          <FormInput
            v-model="v$.minute.$model"
            :disabled="disabled"
            size="large"
            type="number"
            :min="0"
            :max="59"
            @blur="v$.minute.$touch"
            @input="updateWhen"
          />
        </FormGroup>
        <FormGroup
          small-label
          :label="$t('dataSyncPeriodicIntervalForm.second')"
          :error="v$.second.$error"
          required
        >
          <FormInput
            v-model="second"
            :disabled="disabled"
            size="large"
            type="number"
            :min="0"
            :max="59"
            @blur="v$.second.$touch"
            @input="updateWhen"
          />
        </FormGroup>
        <div class="color-neutral">
          {{ timezone }}
        </div>
      </div>
      <p class="control__helper-text">
        <template v-if="values.interval === 'HOURLY'">
          {{ $t('dataSyncPeriodicIntervalForm.whenHourlyHelper') }}
        </template>
        <template v-if="values.interval === 'DAILY'">
          {{ $t('dataSyncPeriodicIntervalForm.whenHelper') }}
        </template>
      </p>
    </template>
    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import moment from '@baserow/modules/core/moment'
import { required, numeric, minValue, maxValue } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'DataSyncPeriodicIntervalForm',
  mixins: [form],
  props: {
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      allowedValues: ['interval', 'when'],
      values: {
        interval: 'MANUAL',
        when: '',
      },
      hour: '',
      minute: '',
      second: '',
    }
  },
  mounted() {
    if (this.values.when) {
      const localTime = moment
        .utc(this.values.when, 'HH:mm:ss')
        .local()
        .format('HH:mm:ss')
      const splitted = localTime.split(':')
      this.hour = parseInt(splitted[0], 10) || 0
      this.minute = parseInt(splitted[1], 10) || 0
      this.second = parseInt(splitted[2], 10) || 0
    } else {
      this.setDefaultTime()
    }
    this.updateWhen()
  },
  methods: {
    setDefaultTime() {
      const localTime = moment().format('HH:mm:ss')
      const splitted = localTime.split(':')
      this.hour = splitted[0]
      this.minute = splitted[1]
      this.second = splitted[2]
    },
    updateWhen() {
      const timeInLocal = `${this.hour}:${this.minute}:${this.second}`
      const timeInUTC = moment(timeInLocal, 'HH:mm:ss').utc().format('HH:mm:ss')
      this.values.when = timeInUTC
    },
  },
  validations() {
    return {
      values: {
        interval: { required },
        when: { required },
      },
      hour: {
        required,
        numeric,
        minValue: minValue(0),
        maxValue: maxValue(24),
      },
      minute: {
        required,
        numeric,
        minValue: minValue(0),
        maxValue: maxValue(59),
      },
      second: {
        required,
        numeric,
        minValue: minValue(0),
        maxValue: maxValue(59),
      },
    }
  },
}
</script>

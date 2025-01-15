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
      <Dropdown v-model="values.interval" :disabled="disabled" size="large">
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
      <div class="flex">
        <FormGroup
          v-if="values.interval === 'DAILY'"
          small-label
          :label="$t('dataSyncPeriodicIntervalForm.hour')"
          :error="$v.hour.$dirty && $v.hour.$error"
          required
        >
          <FormInput
            v-model="hour"
            :disabled="disabled"
            size="large"
            type="number"
            min="0"
            max="23"
            @blur="$v.hour.$touch()"
            @input="updateWhen"
          />
        </FormGroup>
        <FormGroup
          small-label
          :label="$t('dataSyncPeriodicIntervalForm.minute')"
          :error="$v.minute.$dirty && $v.minute.$error"
          required
        >
          <FormInput
            v-model="minute"
            :disabled="disabled"
            size="large"
            type="number"
            min="0"
            max="59"
            @blur="$v.minute.$touch()"
            @input="updateWhen"
          />
        </FormGroup>
        <FormGroup
          small-label
          :label="$t('dataSyncPeriodicIntervalForm.second')"
          :error="$v.second.$dirty && $v.second.$error"
          required
        >
          <FormInput
            v-model="second"
            :disabled="disabled"
            size="large"
            type="number"
            min="0"
            max="59"
            @blur="$v.second.$touch()"
            @input="updateWhen"
          />
        </FormGroup>
      </div>
      <p>
        {{ $t('dataSyncPeriodicIntervalForm.whenHelper') }}
      </p>
    </template>
    <slot></slot>
  </form>
</template>

<script>
import { required, numeric, minValue, maxValue } from 'vuelidate/lib/validators'
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
  data() {
    return {
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
    const splitted = this.values.when.split(':')
    this.hour = splitted[0] || ''
    this.minute = splitted[1] || ''
    this.second = splitted[2] || ''
  },
  methods: {
    updateWhen() {
      this.values.when = `${this.hour}:${this.minute}:${this.second}`
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

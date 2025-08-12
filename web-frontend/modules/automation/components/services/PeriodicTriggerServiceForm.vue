<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('interval')"
      :label="$t('periodicTriggerServiceForm.intervalLabel')"
      :helper-text="$t('periodicTriggerServiceForm.intervalHelper')"
      required
      small-label
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.interval" size="large">
        <DropdownItem
          :name="$t('periodicTriggerServiceForm.everyMinute')"
          value="MINUTE"
        ></DropdownItem>
        <DropdownItem
          :name="$t('periodicTriggerServiceForm.everyHour')"
          value="HOUR"
        ></DropdownItem>
        <DropdownItem
          :name="$t('periodicTriggerServiceForm.everyDay')"
          value="DAY"
        ></DropdownItem>
        <DropdownItem
          :name="$t('periodicTriggerServiceForm.everyWeek')"
          value="WEEK"
        ></DropdownItem>
        <DropdownItem
          :name="$t('periodicTriggerServiceForm.everyMonth')"
          value="MONTH"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>

    <div v-if="values.interval !== null">
      <div class="flex align-items-end margin-bottom-2">
        <FormGroup
          v-if="showHourField"
          small-label
          :label="$t('periodicTriggerServiceForm.hour')"
          :error="fieldHasErrors('hour')"
          required
          class="margin-right-1"
        >
          <FormInput
            v-model="v$.values.hour.$model"
            size="large"
            type="number"
            :min="0"
            :max="23"
            :placeholder="$t('periodicTriggerServiceForm.hourPlaceholder')"
          />
        </FormGroup>
        <FormGroup
          v-if="showMinuteField"
          small-label
          :label="$t('periodicTriggerServiceForm.minute')"
          :error="fieldHasErrors('minute')"
          required
        >
          <FormInput
            v-model="v$.values.minute.$model"
            size="large"
            type="number"
            :min="0"
            :max="59"
            :placeholder="$t('periodicTriggerServiceForm.minutePlaceholder')"
          />
        </FormGroup>
        <div v-if="fieldHasErrors('hour')" class="error">
          {{ v$.values.hour.$errors[0].$message }}
        </div>
        <div v-if="fieldHasErrors('minute')" class="error">
          {{ v$.values.minute.$errors[0].$message }}
        </div>
      </div>
      <FormGroup
        v-if="values.interval === 'WEEK'"
        :error="fieldHasErrors('day_of_week')"
        :label="$t('periodicTriggerServiceForm.dayOfWeek')"
        required
        small-label
        class="margin-bottom-2"
      >
        <Dropdown v-model="values.day_of_week" size="large">
          <DropdownItem
            v-for="(value, key) in daysOfWeek"
            :key="key"
            :name="value"
            :value="parseInt(key)"
          ></DropdownItem>
        </Dropdown>
      </FormGroup>
      <FormGroup
        v-if="values.interval === 'MONTH'"
        :error="fieldHasErrors('day_of_month')"
        :label="$t('periodicTriggerServiceForm.dayOfMonth')"
        required
        small-label
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.values.day_of_month.$model"
          size="large"
          type="number"
          :min="1"
          :max="31"
          :placeholder="$t('periodicTriggerServiceForm.dayOfMonthPlaceholder')"
          @blur="v$.values.day_of_month.$touch()"
        />
        <template #error>
          {{ v$.values.day_of_month.$errors[0].$message }}
        </template>
      </FormGroup>

      <p class="control__helper-text">
        <template v-if="values.interval === 'HOUR'">
          {{ $t('periodicTriggerServiceForm.hourHelper', { timezone }) }}
        </template>
        <template v-else-if="values.interval === 'DAY'">
          {{ $t('periodicTriggerServiceForm.dayHelper', { timezone }) }}
        </template>
        <template v-else-if="values.interval === 'WEEK'">
          {{ $t('periodicTriggerServiceForm.weekHelper', { timezone }) }}
        </template>
        <template v-else-if="values.interval === 'MONTH'">
          {{ $t('periodicTriggerServiceForm.monthHelper', { timezone }) }}
        </template>
      </p>
    </div>

    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { between, required, helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'PeriodicTriggerServiceForm',
  mixins: [form],
  props: {},
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      allowedValues: [
        'interval',
        'minute',
        'hour',
        'day_of_week',
        'day_of_month',
      ],
      values: {
        interval: 'HOUR',
        minute: 0,
        hour: 0,
        day_of_week: 0,
        day_of_month: 1,
      },
    }
  },
  computed: {
    showHourField() {
      return ['DAY', 'WEEK', 'MONTH'].includes(this.values.interval)
    },
    showMinuteField() {
      return ['HOUR', 'DAY', 'WEEK', 'MONTH'].includes(this.values.interval)
    },
    daysOfWeek() {
      return {
        0: this.$t('periodicTriggerServiceForm.monday'),
        1: this.$t('periodicTriggerServiceForm.tuesday'),
        2: this.$t('periodicTriggerServiceForm.wednesday'),
        3: this.$t('periodicTriggerServiceForm.thursday'),
        4: this.$t('periodicTriggerServiceForm.friday'),
        5: this.$t('periodicTriggerServiceForm.saturday'),
        6: this.$t('periodicTriggerServiceForm.sunday'),
      }
    },
  },
  validations() {
    return {
      values: {
        interval: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        minute: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          between: helpers.withMessage(
            this.$t('error.minMaxValueField', { min: 0, max: 59 }),
            between(0, 59)
          ),
        },
        hour: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          between: helpers.withMessage(
            this.$t('error.minMaxValueField', { min: 0, max: 23 }),
            between(0, 23)
          ),
        },
        day_of_month: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          between: helpers.withMessage(
            this.$t('error.minMaxValueField', { min: 0, max: 20 }),
            between(0, 31)
          ),
        },
      },
    }
  },
}
</script>

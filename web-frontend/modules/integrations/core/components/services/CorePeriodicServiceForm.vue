<template>
  <form @submit.prevent>
    <FormGroup
      :error="fieldHasErrors('interval')"
      :label="$t('periodicForm.intervalLabel')"
      :helper-text="intervalText"
      required
      small-label
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.interval" size="large">
        <DropdownItem
          :name="$t('periodicForm.everyMinuteDefault')"
          value="MINUTE"
        />
        <DropdownItem :name="$t('periodicForm.everyHour')" value="HOUR" />
        <DropdownItem :name="$t('periodicForm.everyDay')" value="DAY" />
        <DropdownItem :name="$t('periodicForm.everyWeek')" value="WEEK" />
        <DropdownItem :name="$t('periodicForm.everyMonth')" value="MONTH" />
      </Dropdown>
    </FormGroup>

    <div v-if="values.interval !== null">
      <div class="flex align-items-start margin-bottom-2">
        <FormGroup
          v-if="showMinuteFrequencyField"
          small-label
          :label="$t('periodicForm.minuteFrequency')"
          required
        >
          <FormInput
            v-model="v$.user.minute.$model"
            size="large"
            type="number"
            :min="1"
            :max="59"
            :placeholder="$t('periodicForm.minuteFrequencyPlaceholder')"
          />
        </FormGroup>
        <FormGroup
          v-if="showHourField"
          small-label
          :label="$t('periodicForm.hour')"
          required
          class="margin-right-1"
        >
          <FormInput
            v-model="v$.user.hour.$model"
            size="large"
            type="number"
            :min="0"
            :max="23"
            :placeholder="$t('periodicForm.hourPlaceholder')"
          />
        </FormGroup>
        <FormGroup
          v-if="showMinuteField"
          small-label
          :label="$t('periodicForm.minute')"
          required
        >
          <FormInput
            v-model="v$.user.minute.$model"
            size="large"
            type="number"
            :min="0"
            :max="59"
            :placeholder="$t('periodicForm.minutePlaceholder')"
          />
        </FormGroup>
      </div>

      <div v-if="fieldHasLocalErrors('hour')" class="error margin-bottom-2">
        {{ v$.user.hour.$errors[0].$message }}
      </div>
      <div v-if="fieldHasLocalErrors('minute')" class="error margin-bottom-2">
        {{ v$.user.minute.$errors[0].$message }}
      </div>

      <FormGroup
        v-if="values.interval === 'WEEK'"
        :error="fieldHasLocalErrors('day_of_week')"
        :label="$t('periodicForm.dayOfWeek')"
        required
        small-label
        class="margin-bottom-2"
      >
        <Dropdown v-model="user.day_of_week" size="large">
          <DropdownItem
            v-for="(value, key) in daysOfWeek"
            :key="key"
            :name="value"
            :value="parseInt(key)"
          />
        </Dropdown>
      </FormGroup>

      <FormGroup
        v-if="values.interval === 'MONTH'"
        :error="fieldHasLocalErrors('day_of_month')"
        :label="$t('periodicForm.dayOfMonth')"
        required
        small-label
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.user.day_of_month.$model"
          size="large"
          type="number"
          :min="1"
          :max="31"
          :placeholder="$t('periodicForm.dayOfMonthPlaceholder')"
          @blur="v$.user.day_of_month.$touch()"
        />
        <template #error>
          {{ v$.user.day_of_month.$errors[0].$message }}
        </template>
      </FormGroup>
    </div>
    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { between, required, integer, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'CorePeriodicServiceForm',
  mixins: [form],
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
      // The values stored in UTC timezone (observed by backend).
      values: {
        interval: 'HOUR',
        minute: 0,
        hour: 0,
        day_of_week: 0, // Monday=0..Sunday=6 (UTC)
        day_of_month: 1, // 1..31 (UTC)
      },
      // User-facing values in local timezone.
      user: {
        minute: 0,
        hour: 0,
        day_of_week: 0, // Monday=0..Sunday=6 (LOCAL)
        day_of_month: 1, // 1..31 (LOCAL)
      },
    }
  },
  computed: {
    showMinuteFrequencyField() {
      return this.values.interval === 'MINUTE'
    },
    minimumMinuteFrequency() {
      return this.$config.BASEROW_INTEGRATIONS_PERIODIC_MINUTE_MIN
    },
    showHourField() {
      return ['DAY', 'WEEK', 'MONTH'].includes(this.values.interval)
    },
    showMinuteField() {
      return ['HOUR', 'DAY', 'WEEK', 'MONTH'].includes(this.values.interval)
    },
    intervalText() {
      const context = { timezone: this.timezone }
      switch (this.values.interval) {
        case 'HOUR':
          return this.$t('periodicForm.hourHelper', context)
        case 'DAY':
          return this.$t('periodicForm.dayHelper', context)
        case 'WEEK':
          return this.$t('periodicForm.weekHelper', context)
        case 'MONTH':
          return this.$t('periodicForm.monthHelper', context)
        case null:
          return this.$t('periodicForm.intervalHelper')
        default:
          return ''
      }
    },
    daysOfWeek() {
      return {
        0: this.$t('common.monday'),
        1: this.$t('common.tuesday'),
        2: this.$t('common.wednesday'),
        3: this.$t('common.thursday'),
        4: this.$t('common.friday'),
        5: this.$t('common.saturday'),
        6: this.$t('common.sunday'),
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
      },
      user: {
        minute: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          between: helpers.withMessage(
            this.showMinuteFrequencyField
              ? this.$t('error.minMaxValueField', {
                  min: this.minimumMinuteFrequency,
                  max: 59,
                })
              : this.$t('error.minMaxValueField', { min: 0, max: 59 }),
            this.showMinuteFrequencyField
              ? between(this.minimumMinuteFrequency, 59)
              : between(0, 59)
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
            this.$t('error.minMaxValueField', { min: 1, max: 31 }),
            between(1, 31)
          ),
        },
      },
    }
  },
  watch: {
    'user.minute': 'syncValuesFromUser',
    'user.hour': 'syncValuesFromUser',
    'user.day_of_week': 'syncValuesFromUser',
    'user.day_of_month': 'syncValuesFromUser',
    'values.interval'(newInterval, oldInterval) {
      // When we change *to* MINUTE, we default to the minimum frequency
      // that is granted to this Baserow instance type.
      // When we change *from* MINUTE, reset minute to 0.
      if (
        this.user.minute === 0 &&
        newInterval === 'MINUTE' &&
        oldInterval !== 'MINUTE'
      ) {
        this.user.minute = this.minimumMinuteFrequency
      } else if (newInterval !== 'MINUTE' && oldInterval === 'MINUTE') {
        this.user.minute = 0
      }
      this.syncValuesFromUser()
    },
  },
  mounted() {
    this.syncUserFromValues()
  },
  methods: {
    fieldHasErrors(name) {
      const seg = this.v$.values?.[name]
      return !!(seg && seg.$error)
    },
    fieldHasLocalErrors(name) {
      const seg = this.v$.user?.[name]
      return !!(seg && seg.$error)
    },
    toMondayIndexFromSundayZero(sunZero) {
      return (sunZero + 6) % 7
    },
    localDateForWeekly(monZero, hour, minute) {
      const now = new Date()
      const todayMonZero = (now.getDay() + 6) % 7
      const diff = monZero - todayMonZero
      const d = new Date(now)
      d.setDate(now.getDate() + diff)
      d.setHours(hour, minute, 0, 0)
      return d
    },
    utcPartsFromLocalDate(d) {
      return {
        minute: d.getUTCMinutes(),
        hour: d.getUTCHours(),
        day_of_week: this.toMondayIndexFromSundayZero(d.getUTCDay()),
        day_of_month: d.getUTCDate(),
      }
    },
    syncValuesFromUser() {
      this.v$.$touch()
      if (this.v$.values.interval.$invalid) return
      if (this.showMinuteFrequencyField && this.v$.user.minute.$invalid) return
      if (this.showMinuteField && this.v$.user.minute.$invalid) return
      if (this.showHourField && this.v$.user.hour.$invalid) return
      if (
        this.values.interval === 'MONTH' &&
        this.v$.user.day_of_month.$invalid
      )
        return

      const { interval } = this.values
      const {
        minute,
        hour,
        day_of_week: dayOfWeek,
        day_of_month: dayOfMonth,
      } = this.user

      if (interval === 'MINUTE' || interval === 'HOUR') {
        this.values = { ...this.values, interval, minute }
        return
      }

      if (interval === 'DAY') {
        const base = new Date()
        base.setHours(hour, minute, 0, 0)
        const utc = this.utcPartsFromLocalDate(base)
        this.values = {
          ...this.values,
          interval,
          hour: utc.hour,
          minute: utc.minute,
        }
        return
      }

      if (interval === 'WEEK') {
        const d = this.localDateForWeekly(dayOfWeek, hour, minute)
        const utc = this.utcPartsFromLocalDate(d)
        this.values = {
          ...this.values,
          interval,
          day_of_week: utc.day_of_week,
          hour: utc.hour,
          minute: utc.minute,
        }
        return
      }

      if (interval === 'MONTH') {
        const now = new Date()
        const d = new Date(
          now.getFullYear(),
          now.getMonth(),
          Math.min(dayOfMonth, 31),
          hour,
          minute,
          0,
          0
        )
        const utc = this.utcPartsFromLocalDate(d)
        this.values = {
          ...this.values,
          interval,
          day_of_month: utc.day_of_month,
          hour: utc.hour,
          minute: utc.minute,
        }
      }
    },
    syncUserFromValues() {
      const {
        interval,
        minute,
        hour,
        day_of_week: dayOfWeek,
        day_of_month: dayOfMonth,
      } = this.values

      if (interval === 'MINUTE' || interval === 'HOUR') {
        this.user.minute = minute
        return
      }

      if (interval === 'DAY') {
        const now = new Date()
        const d = new Date(
          Date.UTC(
            now.getUTCFullYear(),
            now.getUTCMonth(),
            now.getUTCDate(),
            hour,
            minute,
            0,
            0
          )
        )
        this.user.hour = d.getHours()
        this.user.minute = d.getMinutes()
        return
      }

      if (interval === 'WEEK') {
        const now = new Date()
        const todayUtcMonZero = (now.getUTCDay() + 6) % 7
        const diff = dayOfWeek - todayUtcMonZero
        const utcCandidate = new Date(
          Date.UTC(
            now.getUTCFullYear(),
            now.getUTCMonth(),
            now.getUTCDate() + diff,
            hour,
            minute,
            0,
            0
          )
        )
        this.user.day_of_week = (utcCandidate.getDay() + 6) % 7
        this.user.hour = utcCandidate.getHours()
        this.user.minute = utcCandidate.getMinutes()
        return
      }

      if (interval === 'MONTH') {
        const now = new Date()
        const utcCandidate = new Date(
          Date.UTC(
            now.getUTCFullYear(),
            now.getUTCMonth(),
            dayOfMonth,
            hour,
            minute,
            0,
            0
          )
        )
        this.user.day_of_month = utcCandidate.getDate()
        this.user.hour = utcCandidate.getHours()
        this.user.minute = utcCandidate.getMinutes()
      }
    },
  },
}
</script>

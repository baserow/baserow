<template>
  <form @submit.prevent>
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
        />
        <DropdownItem
          :name="$t('periodicTriggerServiceForm.everyHour')"
          value="HOUR"
        />
        <DropdownItem
          :name="$t('periodicTriggerServiceForm.everyDay')"
          value="DAY"
        />
        <DropdownItem
          :name="$t('periodicTriggerServiceForm.everyWeek')"
          value="WEEK"
        />
        <DropdownItem
          :name="$t('periodicTriggerServiceForm.everyMonth')"
          value="MONTH"
        />
      </Dropdown>
    </FormGroup>

    <div v-if="values.interval !== null">
      <div class="flex align-items-start margin-bottom-2">
        <FormGroup
          v-if="showHourField"
          small-label
          :label="$t('periodicTriggerServiceForm.hour')"
          required
          class="margin-right-1"
        >
          <FormInput
            v-model="v$.user.hour.$model"
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
          required
        >
          <FormInput
            v-model="v$.user.minute.$model"
            size="large"
            type="number"
            :min="0"
            :max="59"
            :placeholder="$t('periodicTriggerServiceForm.minutePlaceholder')"
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
        :label="$t('periodicTriggerServiceForm.dayOfWeek')"
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
        :label="$t('periodicTriggerServiceForm.dayOfMonth')"
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
          :placeholder="$t('periodicTriggerServiceForm.dayOfMonthPlaceholder')"
          @blur="v$.user.day_of_month.$touch()"
        />
        <template #error>
          {{ v$.user.day_of_month.$errors[0].$message }}
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
      },
      user: {
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
    'values.interval': 'syncValuesFromUser',
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

      if (interval === 'MINUTE') {
        this.values = { ...this.values, interval }
        return
      }

      if (interval === 'HOUR') {
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

    // ---- One-time UTC → LOCAL (on mount) ----
    syncUserFromValues() {
      const {
        interval,
        minute,
        hour,
        day_of_week: dayOfWeek,
        day_of_month: dayOfMonth,
      } = this.values

      if (interval === 'MINUTE') {
        return
      }

      if (interval === 'HOUR') {
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
        this.user.hour = d.getHours() // local
        this.user.minute = d.getMinutes() // local
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
        this.user.day_of_week = (utcCandidate.getDay() + 6) % 7 // local Mon=0..Sun=6
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
        this.user.day_of_month = utcCandidate.getDate() // local date (may shift)
        this.user.hour = utcCandidate.getHours()
        this.user.minute = utcCandidate.getMinutes()
      }
    },
  },
}
</script>

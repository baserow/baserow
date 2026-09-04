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
            v-model="v$.values.minute.$model"
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
            v-model="v$.values.hour.$model"
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
            v-model="v$.values.minute.$model"
            size="large"
            type="number"
            :min="0"
            :max="59"
            :placeholder="$t('periodicForm.minutePlaceholder')"
          />
        </FormGroup>
      </div>

      <div v-if="fieldHasErrors('hour')" class="error margin-bottom-2">
        {{ v$.values.hour.$errors[0].$message }}
      </div>
      <div v-if="fieldHasErrors('minute')" class="error margin-bottom-2">
        {{ v$.values.minute.$errors[0].$message }}
      </div>

      <FormGroup
        v-if="values.interval === 'WEEK'"
        :label="$t('periodicForm.dayOfWeek')"
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
          />
        </Dropdown>
      </FormGroup>

      <FormGroup
        v-if="values.interval === 'MONTH'"
        :error="fieldHasErrors('day_of_month')"
        :label="$t('periodicForm.dayOfMonth')"
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
          :placeholder="$t('periodicForm.dayOfMonthPlaceholder')"
          @blur="v$.values.day_of_month.$touch()"
        />
        <template #error>
          {{ v$.values.day_of_month.$errors[0].$message }}
        </template>
      </FormGroup>

      <FormGroup
        v-if="showTimezoneField"
        :label="$t('periodicForm.timezone')"
        :helper-text="$t('periodicForm.timezoneHelper')"
        required
        small-label
        class="margin-bottom-2"
      >
        <PaginatedDropdown
          :value="values.timezone"
          :fetch-page="fetchTimezonePage"
          :add-empty-item="false"
          :initial-display-name="values.timezone"
          :fetch-on-open="true"
          :debounce-time="20"
          :page-size="pageSize"
          :fixed-items="true"
          @input="(timezone) => (values.timezone = timezone)"
        ></PaginatedDropdown>
      </FormGroup>
    </div>
    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { between, required, integer, helpers } from '@vuelidate/validators'
import moment from '@baserow/modules/core/moment'
import form from '@baserow/modules/core/mixins/form'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'

export default {
  name: 'CorePeriodicServiceForm',
  components: { PaginatedDropdown },
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      pageSize: 100,
      allowedValues: [
        'interval',
        'timezone',
        'minute',
        'hour',
        'day_of_week',
        'day_of_month',
      ],
      // The schedule exactly as the user entered it. The backend resolves these
      // against `timezone` for every run, so they're sent through unconverted.
      values: {
        interval: 'HOUR',
        timezone: moment.tz.guess(),
        minute: 0,
        hour: 0,
        day_of_week: 0, // Monday=0..Sunday=6
        day_of_month: 1, // 1..31
      },
    }
  },
  computed: {
    showMinuteFrequencyField() {
      return this.values.interval === 'MINUTE'
    },
    minimumMinuteFrequency() {
      return this.$config.public.baserowIntegrationsPeriodicMinuteMin
    },
    showHourField() {
      return ['DAY', 'WEEK', 'MONTH'].includes(this.values.interval)
    },
    showMinuteField() {
      return ['HOUR', 'DAY', 'WEEK', 'MONTH'].includes(this.values.interval)
    },
    showTimezoneField() {
      // A MINUTE interval is a frequency rather than a time of day, and an HOUR
      // interval only picks a minute past the hour, so neither depends on the
      // timezone. Every offset in use is a whole number of minutes.
      return ['DAY', 'WEEK', 'MONTH'].includes(this.values.interval)
    },
    intervalText() {
      switch (this.values.interval) {
        case 'HOUR':
          return this.$t('periodicForm.hourHelper')
        case 'DAY':
          return this.$t('periodicForm.dayHelper')
        case 'WEEK':
          return this.$t('periodicForm.weekHelper')
        case 'MONTH':
          return this.$t('periodicForm.monthHelper')
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
    'values.interval'(newInterval, oldInterval) {
      if (newInterval === 'MINUTE' && oldInterval !== 'MINUTE') {
        // When changing the interval *to* MINUTE, set the minute field to the
        // minimum allowed frequency for this Baserow instance type.
        this.values.minute = this.minimumMinuteFrequency
      } else if (newInterval !== 'MINUTE' && oldInterval === 'MINUTE') {
        // Otherwise if we're changing *from* MINUTE, then reset the `minute` to 0.
        this.values.minute = 0
      }
    },
  },
  methods: {
    getDefaultValues() {
      const defaultValues = form.methods.getDefaultValues.call(this)
      // A trigger without an interval has never been scheduled, so it has no
      // existing schedule to preserve and can default to the user's own timezone.
      // The backend defaults to UTC instead, because that's what keeps schedules
      // made before the timezone was configurable running at the same times.
      if (!defaultValues.interval) {
        defaultValues.timezone = moment.tz.guess()
      }
      return defaultValues
    },
    fieldHasErrors(name) {
      const seg = this.v$.values?.[name]
      return !!(seg && seg.$error)
    },
    fetchTimezonePage(page, search) {
      const pageSize = this.pageSize
      const start = (page - 1) * pageSize
      const results = this.filterTimezones(search || '')
      // The paginated dropdown expects a HTTP response-like object.
      return {
        data: {
          count: results.length,
          next: results.length > start + pageSize ? page + 1 : null,
          previous: page > 1 ? page - 1 : null,
          results: results.slice(start, start + pageSize).map((timezone) => {
            return {
              id: timezone,
              value: timezone,
            }
          }),
        },
      }
    },
    filterTimezones(value) {
      return moment.tz.names().filter((timezone) => {
        return timezone.toLowerCase().includes(value.toLowerCase())
      })
    },
  },
}
</script>

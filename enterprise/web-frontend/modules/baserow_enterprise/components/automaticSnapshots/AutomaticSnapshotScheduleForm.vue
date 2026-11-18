<template>
  <div class="automatic-snapshot-schedule-form">
    <FormGroup
      :label="$t('automaticSnapshots.repeatLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <SegmentControl
        :segments="intervalSegments"
        :active-index="intervalIndex"
        class="automatic-snapshot-schedule-form__segments"
        @update:active-index="selectInterval"
      ></SegmentControl>
    </FormGroup>

    <FormGroup
      v-if="values.interval === 'WEEK'"
      :label="$t('automaticSnapshots.weekdayLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <SegmentControl
        :segments="weekdaySegments"
        :active-index="values.day_of_week"
        type="rounded"
        @update:active-index="values.day_of_week = $event"
      ></SegmentControl>
    </FormGroup>

    <div class="automatic-snapshot-schedule-form__row margin-bottom-2">
      <FormGroup
        v-if="values.interval === 'MONTH'"
        :error="fieldHasErrors('day_of_month')"
        :label="$t('automaticSnapshots.dayOfMonthLabel')"
        :helper-text="$t('automaticSnapshots.dayOfMonthHelper')"
        small-label
        required
      >
        <FormInput
          v-model="v$.values.day_of_month.$model"
          type="number"
          size="large"
          :min="1"
          :max="31"
          @blur="v$.values.day_of_month.$touch()"
        />
        <template #error>
          {{ getFirstErrorMessage('day_of_month') }}
        </template>
      </FormGroup>

      <FormGroup
        v-if="isLocalTime"
        :error="fieldHasErrors('time')"
        :label="$t('automaticSnapshots.timeLabel')"
        small-label
        required
      >
        <FormInput
          v-model="v$.values.time.$model"
          type="time"
          size="large"
          @blur="v$.values.time.$touch()"
        />
        <template #error>
          {{ getFirstErrorMessage('time') }}
        </template>
      </FormGroup>
      <FormGroup
        v-else
        :error="fieldHasErrors('minute')"
        :label="
          values.interval === 'MINUTE'
            ? $t('automaticSnapshots.everyMinutesLabel')
            : $t('automaticSnapshots.minutePastLabel')
        "
        small-label
        required
      >
        <FormInput
          v-model="v$.values.minute.$model"
          type="number"
          size="large"
          :min="minuteMin"
          :max="59"
          @blur="v$.values.minute.$touch()"
        />
        <template #error>
          {{ getFirstErrorMessage('minute') }}
        </template>
      </FormGroup>

      <FormGroup
        v-if="isLocalTime"
        :label="$t('automaticSnapshots.timezoneLabel')"
        small-label
        required
      >
        <PaginatedDropdown
          :value="values.timezone"
          :fetch-page="fetchTimezonePage"
          :add-empty-item="false"
          :initial-display-name="values.timezone"
          :fetch-on-open="true"
          :debounce-time="20"
          :page-size="timezonePageSize"
          :fixed-items="true"
          size="large"
          @input="values.timezone = $event"
        ></PaginatedDropdown>
      </FormGroup>
    </div>

    <div class="automatic-snapshot-schedule-form__keep-note">
      <i class="iconoir-info-empty"></i>
      <span>{{ $t('automaticSnapshots.keepNote') }}</span>
    </div>

    <div v-if="preview" class="automatic-snapshot-schedule-form__preview">
      <i class="iconoir-clock"></i>
      <div>
        <div class="automatic-snapshot-schedule-form__preview-title">
          {{ preview.summary }}
        </div>
        <div>{{ preview.nextRun }}</div>
      </div>
    </div>

    <slot></slot>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { between, helpers, integer, required } from '@vuelidate/validators'
import moment from '@baserow/modules/core/moment'
import form from '@baserow/modules/core/mixins/form'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import {
  LOCAL_TIME_INTERVALS,
  describeSchedule,
  formatRunTime,
  getAllowedIntervals,
  getNextRun,
} from '@baserow_enterprise/utils/automaticSnapshots'

const TIME_PATTERN = /^([01]?\d|2[0-3]):([0-5]\d)$/

export default {
  name: 'AutomaticSnapshotScheduleForm',
  components: { PaginatedDropdown },
  mixins: [form],
  props: {
    minIntervalMinutes: {
      type: Number,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      timezonePageSize: 100,
      allowedValues: [
        'interval',
        'timezone',
        'minute',
        'hour',
        'day_of_week',
        'day_of_month',
      ],
      values: {
        interval: 'DAY',
        timezone: moment.tz.guess(),
        minute: 0,
        hour: 0,
        day_of_week: 0,
        day_of_month: 1,
        // The hour and minute of the day, edited as one field.
        time: '00:00',
      },
    }
  },
  computed: {
    intervals() {
      return getAllowedIntervals(this.minIntervalMinutes)
    },
    intervalSegments() {
      const labels = {
        MINUTE: this.$t('automaticSnapshots.repeatMinutes'),
        HOUR: this.$t('automaticSnapshots.repeatHourly'),
        DAY: this.$t('automaticSnapshots.repeatDaily'),
        WEEK: this.$t('automaticSnapshots.repeatWeekly'),
        MONTH: this.$t('automaticSnapshots.repeatMonthly'),
      }
      return this.intervals.map((interval) => ({ label: labels[interval] }))
    },
    intervalIndex() {
      return this.intervals.indexOf(this.values.interval)
    },
    weekdaySegments() {
      return [
        'common.monday',
        'common.tuesday',
        'common.wednesday',
        'common.thursday',
        'common.friday',
        'common.saturday',
        'common.sunday',
      ].map((key) => ({ label: this.$t(key).slice(0, 2) }))
    },
    isLocalTime() {
      return LOCAL_TIME_INTERVALS.includes(this.values.interval)
    },
    minuteMin() {
      return this.values.interval === 'MINUTE' ? this.minIntervalMinutes : 0
    },
    scheduleValues() {
      const values = { ...this.values }
      const match = TIME_PATTERN.exec(values.time)
      if (this.isLocalTime && match) {
        values.hour = parseInt(match[1])
        values.minute = parseInt(match[2])
      }
      values.minute = parseInt(values.minute)
      values.day_of_month = parseInt(values.day_of_month)
      delete values.time
      return values
    },
    preview() {
      if (this.v$.$invalid) {
        return null
      }
      const nextRun = getNextRun(this.scheduleValues)
      if (!nextRun) {
        return null
      }
      const summary = describeSchedule(this.scheduleValues, (...args) =>
        this.$t(...args)
      )
      return {
        summary: this.isLocalTime
          ? `${summary}, ${this.values.timezone}`
          : summary,
        nextRun: this.$t('automaticSnapshots.nextRun', {
          date: formatRunTime(
            this.scheduleValues,
            nextRun,
            'dddd D MMMM, HH:mm'
          ),
        }),
      }
    },
  },
  validations() {
    const minuteMax = 59
    return {
      values: {
        time: this.isLocalTime
          ? {
              required: helpers.withMessage(
                this.$t('error.requiredField'),
                required
              ),
              format: helpers.withMessage(
                this.$t('automaticSnapshots.timeFormatError'),
                (value) => TIME_PATTERN.test(value)
              ),
            }
          : {},
        minute: this.isLocalTime
          ? {}
          : {
              required: helpers.withMessage(
                this.$t('error.requiredField'),
                required
              ),
              integer: helpers.withMessage(
                this.$t('error.integerField'),
                integer
              ),
              between: helpers.withMessage(
                this.$t('error.minMaxValueField', {
                  min: this.minuteMin,
                  max: minuteMax,
                }),
                between(this.minuteMin, minuteMax)
              ),
            },
        day_of_month:
          this.values.interval === 'MONTH'
            ? {
                required: helpers.withMessage(
                  this.$t('error.requiredField'),
                  required
                ),
                between: helpers.withMessage(
                  this.$t('error.minMaxValueField', { min: 1, max: 31 }),
                  between(1, 31)
                ),
              }
            : {},
      },
    }
  },
  created() {
    const hour = String(this.values.hour).padStart(2, '0')
    const minute = String(this.values.minute).padStart(2, '0')
    this.values.time = `${hour}:${minute}`
  },
  methods: {
    selectInterval(index) {
      const interval = this.intervals[index]
      const wasLocalTime = this.isLocalTime
      this.values.interval = interval
      if (interval === 'MINUTE') {
        this.values.minute = this.minIntervalMinutes
      } else if (wasLocalTime && interval === 'HOUR') {
        // Keeps the minute of the time of day, so the schedule stays spread out.
        const match = TIME_PATTERN.exec(this.values.time)
        this.values.minute = match ? parseInt(match[2]) : 0
      }
    },
    getFormValues() {
      return this.scheduleValues
    },
    fetchTimezonePage(page, search) {
      const start = (page - 1) * this.timezonePageSize
      const results = moment.tz
        .names()
        .filter((timezone) =>
          timezone.toLowerCase().includes((search || '').toLowerCase())
        )
      // The paginated dropdown expects a HTTP response-like object.
      return {
        data: {
          count: results.length,
          next:
            results.length > start + this.timezonePageSize ? page + 1 : null,
          previous: page > 1 ? page - 1 : null,
          results: results
            .slice(start, start + this.timezonePageSize)
            .map((timezone) => ({ id: timezone, value: timezone })),
        },
      }
    },
  },
}
</script>

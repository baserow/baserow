<template>
  <div>
    <FormGroup
      :label="$t('fieldDateSubForm.dateFormatLabel')"
      small-label
      required
      :error="v$.values.date_format.$error"
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="v$.values.date_format.$model"
        :error="v$.values.date_format.$error"
        :fixed-items="true"
        @hide="v$.values.date_format.$touch"
      >
        <DropdownItem
          :name="$t('fieldDateSubForm.dateFormatEuropean') + ' (20/02/2020)'"
          value="EU"
        ></DropdownItem>
        <DropdownItem
          :name="$t('fieldDateSubForm.dateFormatUS') + ' (02/20/2020)'"
          value="US"
        ></DropdownItem>
        <DropdownItem
          :name="$t('fieldDateSubForm.dateFormatISO') + ' (2020-02-20)'"
          value="ISO"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>

    <Checkbox v-model="values.date_include_time">{{
      $t('fieldDateSubForm.includeTimeLabel')
    }}</Checkbox>

    <FormGroup
      v-show="values.date_include_time"
      required
      small-label
      :label="$t('fieldDateSubForm.timeFormatLabel')"
      class="margin-bottom-2 margin-top-1"
    >
      <Dropdown
        v-model="v$.values.date_time_format.$model"
        :fixed-items="true"
        @hide="v$.values.date_time_format.$touch"
      >
        <DropdownItem
          :name="$t('fieldDateSubForm.24Hour') + ' (23:00)'"
          value="24"
        ></DropdownItem>
        <DropdownItem
          :name="$t('fieldDateSubForm.12Hour') + ' (11:00 PM)'"
          value="12"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>

    <Checkbox
      v-show="values.date_include_time"
      :checked="values.date_force_timezone !== null"
      @input="toggleForceTimezone()"
      >{{ $t('fieldDateSubForm.forceTimezoneLabel') }}</Checkbox
    >

    <FormGroup
      v-show="values.date_include_time && values.date_force_timezone !== null"
      required
      small-label
      :label="$t('fieldDateSubForm.forceTimezoneValue')"
      class="margin-top-1 margin-bottom-2"
    >
      <PaginatedDropdown
        :value="values.date_force_timezone"
        :fetch-page="fetchTimezonePage"
        :add-empty-item="false"
        :initial-display-name="defaultValues.date_force_timezone"
        :fetch-on-open="true"
        :debounce-time="20"
        :page-size="pageSize"
        :fixed-items="true"
        @input="(timezone) => (values.date_force_timezone = timezone)"
      ></PaginatedDropdown>
    </FormGroup>

    <Checkbox
      v-show="
        !onCreate &&
        !defaultValues.read_only &&
        values.date_include_time &&
        utcOffsetDiff !== 0
      "
      :checked="values.date_force_timezone_offset !== null"
      @input="toggleForceTimezoneOffset()"
      >{{
        $t(
          utcOffsetDiff > 0
            ? 'fieldDateSubForm.addTimezoneOffsetLabel'
            : 'fieldDateSubForm.subTimezoneOffsetLabel',
          { utcOffsetDiff: Math.abs(utcOffsetDiff) }
        )
      }}</Checkbox
    >
    <Checkbox v-model="values.date_show_tzinfo" class="margin-top-1">{{
      $t('fieldDateSubForm.showTimezoneLabel')
    }}</Checkbox>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import { required } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'

export default {
  name: 'FieldDateSubForm',
  components: {
    PaginatedDropdown,
  },
  mixins: [form, fieldSubForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'date_format',
        'date_include_time',
        'date_time_format',
        'date_show_tzinfo',
        'date_force_timezone',
        'date_force_timezone_offset',
      ],
      values: {
        date_format: 'EU',
        date_include_time: false,
        date_time_format: '24',
        date_show_tzinfo: false,
        date_force_timezone: null,
        date_force_timezone_offset: null,
      },
      pageSize: 100,
    }
  },
  computed: {
    onCreate() {
      return (
        this.defaultValues.name === null ||
        this.defaultValues.name === undefined
      )
    },
    utcOffsetDiff() {
      if (this.values.date_force_timezone === null) {
        return 0
      }
      const defaultTz = this.defaultValues.date_force_timezone
        ? this.defaultValues.date_force_timezone
        : moment.tz.guess()
      const defaultOffset = moment.tz(defaultTz).utcOffset()
      const offset = moment.tz(this.values.date_force_timezone).utcOffset()
      return defaultOffset - offset
    },
  },
  watch: {
    'values.date_time_format'(newValue, oldValue) {
      // For formula fields date_time_format is nullable, ensure it is set to the
      // default otherwise we will be sending nulls to the server.
      if (newValue == null) {
        this.values.date_time_format = '24'
      }
    },
    'values.date_include_time'(newValue, oldValue) {
      // For formula fields date_include_time is nullable, ensure it is set to the
      // default otherwise we will be sending nulls to the server.
      if (newValue == null) {
        this.values.date_include_time = false
      }
    },
    'values.date_show_tzinfo'(newValue, oldValue) {
      // For formula fields date_show_tzinfo is nullable, ensure it is set to the
      // default otherwise we will be sending nulls to the server.
      if (newValue == null) {
        this.values.date_show_tzinfo = false
      }
    },
  },
  methods: {
    fetchTimezonePage(page, search) {
      const pageSize = this.pageSize
      const start = (page - 1) * pageSize
      const results = this.filterTimezones(search || '')
      // The paginate dropdown expects a HTTP response-like object with these properties
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
    toggleForceTimezone() {
      if (this.values.date_force_timezone === null) {
        this.values.date_force_timezone = moment.tz.guess()
      } else {
        this.values.date_force_timezone = null
      }
    },
    toggleForceTimezoneOffset() {
      if (this.values.date_force_timezone_offset === null) {
        this.values.date_force_timezone_offset = this.utcOffsetDiff
      } else {
        this.values.date_force_timezone_offset = null
      }
    },
  },
  validations() {
    return {
      values: {
        date_format: { required },
        date_time_format: { required },
        date_show_tzinfo: { required },
        date_force_timezone: {},
        date_force_timezone_offset: {},
      },
    }
  },
}
</script>

<template>
  <div>
    <FormGroup
      :label="$t('fieldDateSubForm.dateFormatLabel')"
      small-label
      required
      :error="v$.date_format.$error"
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="v$.date_format.$model"
        :error="v$.date_format.$error"
        :fixed-items="true"
        @hide="v$.date_format.$touch"
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

    <Checkbox v-model="v$.date_include_time.$model">{{
      $t('fieldDateSubForm.includeTimeLabel')
    }}</Checkbox>

    <FormGroup
      v-show="v$.date_include_time.$model"
      required
      small-label
      :label="$t('fieldDateSubForm.timeFormatLabel')"
      class="margin-bottom-2 margin-top-1"
    >
      <Dropdown
        v-model="v$.date_time_format.$model"
        :fixed-items="true"
        @hide="v$.date_time_format.$touch"
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
      v-show="v$.date_include_time.$model"
      :checked="v$.date_force_timezone.$model !== null"
      @input="toggleForceTimezone()"
      >{{ $t('fieldDateSubForm.forceTimezoneLabel') }}</Checkbox
    >

    <FormGroup
      v-show="
        v$.date_include_time.$model && v$.date_force_timezone.$model !== null
      "
      required
      small-label
      :label="$t('fieldDateSubForm.forceTimezoneValue')"
      class="margin-top-1 margin-bottom-2"
    >
      <PaginatedDropdown
        :value="v$.date_force_timezone.$model"
        :fetch-page="fetchTimezonePage"
        :add-empty-item="false"
        :initial-display-name="defaultValues.date_force_timezone"
        :fetch-on-open="true"
        :debounce-time="100"
        :fixed-items="true"
        @input="(timezone) => (values.date_force_timezone = timezone)"
      ></PaginatedDropdown>
    </FormGroup>

    <Checkbox
      v-show="
        !onCreate &&
        !defaultValues.read_only &&
        v$.date_include_time.$model &&
        utcOffsetDiff !== 0
      "
      :checked="v$.date_force_timezone_offset.$model !== null"
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
    <Checkbox v-model="v$.date_show_tzinfo.$model" class="margin-top-1">{{
      $t('fieldDateSubForm.showTimezoneLabel')
    }}</Checkbox>
  </div>
</template>

<script>
import moment from '@baserow/modules/core/moment'
import { required } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'

export default {
  name: 'FieldDateSubForm',
  components: {
    PaginatedDropdown,
  },
  mixins: [form, fieldSubForm],
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
      values: null,
      v$: null,
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
        this.v$.date_time_format.$model = '24'
      }
    },
    'values.date_include_time'(newValue, oldValue) {
      // For formula fields date_include_time is nullable, ensure it is set to the
      // default otherwise we will be sending nulls to the server.
      if (newValue == null) {
        this.values.date_include_time.$model = false
      }
    },
    'values.date_show_tzinfo'(newValue, oldValue) {
      // For formula fields date_show_tzinfo is nullable, ensure it is set to the
      // default otherwise we will be sending nulls to the server.
      if (newValue == null) {
        this.values.date_show_tzinfo.$model = false
      }
    },
  },
  created() {
    const values = reactive({
      date_format: 'EU',
      date_include_time: false,
      date_time_format: '24',
      date_show_tzinfo: false,
      date_force_timezone: null,
      date_force_timezone_offset: null,
    })

    const rules = computed(() => ({
      date_format: { required },
      date_include_time: {},
      date_time_format: { required },
      date_show_tzinfo: { required },
      date_force_timezone: {},
      date_force_timezone_offset: {},
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    fetchTimezonePage(page, search) {
      const pageSize = 20
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
}
</script>

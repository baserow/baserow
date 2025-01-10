<template>
  <div>
    <form v-if="dateFields.length > 0" @submit.prevent="submit">
      <Error
        class="timeline-date-settings-form__alert"
        :error="incompatibleFieldsError"
      ></Error>

      <FormGroup
        :label="$t('timelineDateSettingsForm.startDateField')"
        :error="v$.values.startDateFieldId.$error"
        small-label
        required
        class="margin-bottom-2"
      >
        <Dropdown
          v-model="v$.values.startDateFieldId.$model"
          fixed-items
          :show-search="true"
          :disabled="readOnly"
          :placeholder="readOnly ? ' ' : $t('action.makeChoice')"
        >
          <DropdownItem :key="null" name="" :value="null">
            <div :style="{ height: '15px' }"></div>
          </DropdownItem>
          <DropdownItem
            v-for="dateField in availableStartDateFields"
            :key="dateField.id"
            :name="getDateFieldNameAndAttrs(dateField)"
            :value="dateField.id"
            :icon="fieldIcon(dateField.type)"
          >
          </DropdownItem>
        </Dropdown>

        <template #error>
          <span v-if="v$.values.startDateFieldId.required.$invalid">
            {{ $t('error.requiredField') }}
          </span>
        </template>
      </FormGroup>
      <FormGroup
        :label="$t('timelineDateSettingsForm.endDateField')"
        :error="fieldHasErrors('endDateFieldId')"
        small-label
        required
      >
        <Dropdown
          v-model="v$.values.endDateFieldId.$model"
          fixed-items
          :show-search="true"
          :disabled="readOnly"
        >
          <DropdownItem :key="null" name="" :value="null">
            <div :style="{ height: '15px' }"></div>
          </DropdownItem>
          <DropdownItem
            v-for="dateField in availableEndDateFields"
            :key="dateField.id"
            :name="getDateFieldNameAndAttrs(dateField)"
            :value="dateField.id"
            :icon="fieldIcon(dateField.type)"
          >
          </DropdownItem>
        </Dropdown>

        <template #error>
          {{ v$.values.endDateFieldId.$errors[0]?.$message }}
        </template>
      </FormGroup>
      <slot></slot>
    </form>
    <p v-else>
      {{ $t('timelineDateSettingsForm.noCompatibleDateFields') }}
    </p>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, getCurrentInstance } from 'vue'
import { required, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import {
  filterDateFields,
  getDateField,
  dateFieldsAreCompatible,
} from '@baserow_premium/utils/timeline'

export default {
  name: 'TimelineDateSettingsForm',
  mixins: [form],
  props: {
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  setup() {
    const instance = getCurrentInstance()
    const values = reactive({
      values: {
        startDateFieldId: instance.proxy.view.start_date_field || null,
        endDateFieldId: instance.proxy.view.end_date_field || null,
      },
    })

    const rules = {
      values: {
        startDateFieldId: {
          required: helpers.withMessage(
            instance.proxy.$t('error.requiredField'),
            required
          ),
        },
        endDateFieldId: {
          required: helpers.withMessage(
            instance.proxy.$t('error.requiredField'),
            required
          ),
        },
      },
    }

    return {
      values: values.values,
      v$: useVuelidate(rules, values, { $lazy: true }),
      loading: false,
    }
  },
  data() {
    return {
      incompatibleFieldsError: {
        visible: false,
        title: this.$t('timelineDateSettingsForm.incompatibleFieldsErrorTitle'),
        message: this.$t(
          'timelineDateSettingsForm.incompatibleFieldsErrorMessage'
        ),
      },
    }
  },
  computed: {
    dateFields() {
      return filterDateFields(this.$registry, this.fields)
    },
    availableStartDateFields() {
      return this.dateFields.filter((f) => f.id !== this.values.endDateFieldId)
    },
    availableEndDateFields() {
      return this.dateFields.filter(
        (f) => f.id !== this.values.startDateFieldId
      )
    },
    startDateField() {
      const fieldId = this.values.startDateFieldId
      return getDateField(this.$registry, this.fields, fieldId)
    },
    endDateField() {
      const fieldId = this.values.endDateFieldId
      return getDateField(this.$registry, this.fields, fieldId)
    },
  },
  watch: {
    'view.start_date_field'(value) {
      if (this.values.startDateFieldId === null) {
        this.values.startDateFieldId = value
      }
    },
    'view.end_date_field'(value) {
      if (this.values.endDateFieldId === null) {
        this.values.endDateFieldId = value
      }
    },
    'values.startDateFieldId': {
      handler(value) {
        const start = getDateField(this.$registry, this.fields, value)
        const end = this.endDateField
        if (start && end) {
          this.incompatibleFieldsError.visible = !dateFieldsAreCompatible(
            start,
            end
          )
        }
      },
      immediate: true,
    },
    'values.endDateFieldId': {
      handler(value) {
        const start = this.startDateField
        const end = getDateField(this.$registry, this.fields, value)
        if (start && end) {
          this.incompatibleFieldsError.visible = !dateFieldsAreCompatible(
            start,
            end
          )
        }
      },
      immediate: true,
    },
  },
  methods: {
    fieldIcon(type) {
      const ft = this.$registry.get('field', type)
      return ft?.getIconClass() || 'calendar-alt'
    },
    getDateFieldNameAndAttrs(field) {
      if (!field.date_include_time) {
        return field.name + ` (${this.$t('timelineDateSettingsForm.dateOnly')})`
      } else if (field.date_force_timezone) {
        const tz = this.$t('timelineDateSettingsForm.forceTimezone', {
          timezone: field.date_force_timezone,
        })
        return field.name + ` (${tz})`
      } else {
        return (
          field.name + ` (${this.$t('timelineDateSettingsForm.includeTime')})`
        )
      }
    },
    dateSettingsAreValid() {
      const startId = this.values.startDateFieldId
      const start = getDateField(this.$registry, this.fields, startId)
      const endId = this.values.endDateFieldId
      const end = getDateField(this.$registry, this.fields, endId)
      return start && end && dateFieldsAreCompatible(start, end)
    },
    submit() {
      this.v$.$touch()
      if (this.v$.$invalid || !this.dateSettingsAreValid()) {
        return
      }
      this.$emit('submitted', this.values)
    },
  },
}
</script>

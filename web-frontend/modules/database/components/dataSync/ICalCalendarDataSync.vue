<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('ical_url')"
      :helper-text="$t('iCalCalendarDataSync.description')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('iCalCalendarDataSync.name') }}</template>
      <FormInput
        ref="ical_url"
        v-model="v$.values.ical_url.$model"
        size="large"
        :error="fieldHasErrors('ical_url')"
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="v$.values.ical_url.$touch"
      >
      </FormInput>
      <template #error>
        {{ v$.values.ical_url.$errors[0]?.$message }}
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { required, url, helpers } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'ICalCalendarDataSync',
  mixins: [form],
  props: {
    update: {
      type: Boolean,
      required: false,
      default: false,
    },
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
      allowedValues: ['ical_url'],
      values: {
        ical_url: '',
      },
    }
  },
  validations() {
    return {
      values: {
        ical_url: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          url: helpers.withMessage(this.$t('error.invalidURL'), url),
        },
      },
    }
  },
}
</script>

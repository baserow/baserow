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
        v-model="values.ical_url"
        size="large"
        :error="fieldHasErrors('ical_url')"
        :disabled="disabled"
        @focus.once="$event.target.select()"
        @blur="$v.values.ical_url.$touch()"
      >
      </FormInput>
      <template #error>
        <div v-if="$v.values.ical_url.$dirty && !$v.values.ical_url.required">
          {{ $t('error.requiredField') }}
        </div>
        <div v-else-if="$v.values.ical_url.$dirty && !$v.values.ical_url.url">
          {{ $t('error.invalidURL') }}
        </div>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { required, url } from 'vuelidate/lib/validators'

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
  data() {
    return {
      allowedValues: ['ical_url'],
      values: {
        ical_url: '',
      },
    }
  },
  validations: {
    values: {
      ical_url: { required, url },
    },
  },
}
</script>

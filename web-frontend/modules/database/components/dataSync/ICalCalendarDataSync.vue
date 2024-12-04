<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="v$.ical_url.$error"
      :helper-text="$t('iCalCalendarDataSync.description')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>{{ $t('iCalCalendarDataSync.name') }}</template>
      <FormInput
        ref="ical_url"
        v-model="v$.ical_url.$model"
        size="large"
        :error="v$.ical_url.$error"
        @focus.once="$event.target.select()"
        @blur="v$.ical_url.$touch"
      >
      </FormInput>
      <template #error>
        <div v-if="v$.ical_url.required.$invalid">
          {{ $t('error.requiredField') }}
        </div>
        <div v-else-if="v$.ical_url.url.$invalid">
          {{ $t('error.invalidURL') }}
        </div>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { required, url } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'ICalCalendarDataSync',
  mixins: [form],
  data() {
    return {
      allowedValues: ['ical_url'],
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      ical_url: '',
    })

    const rules = computed(() => ({
      ical_url: {
        required,
        url,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>

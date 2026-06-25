<template>
  <div>
    <FormGroup
      class="margin-bottom-2"
      small-label
      :label="$t('coreManualTriggerServiceForm.responseOptionsLabel')"
    >
      <Checkbox v-model="values.wait_for_response">
        {{ $t('coreManualTriggerServiceForm.waitForResponse') }}
      </Checkbox>
      <p>{{ $t('coreManualTriggerServiceForm.waitForResponseDescription') }}</p>
    </FormGroup>

    <FormGroup
      v-if="values.wait_for_response"
      class="margin-bottom-2"
      small-label
      required
      :label="$t('coreManualTriggerServiceForm.responseTimeout')"
      :error-message="getFirstErrorMessage('response_timeout_seconds')"
    >
      <FormInput
        v-model="v$.values.response_timeout_seconds.$model"
        :to-value="(value) => parseInt(value)"
        type="number"
      >
        <template #suffix>{{
          $t('coreManualTriggerServiceForm.seconds')
        }}</template>
      </FormInput>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import {
  helpers,
  integer,
  maxValue,
  minValue,
  required,
} from '@vuelidate/validators'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'CoreManualTriggerServiceForm',
  components: { Checkbox },
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['wait_for_response', 'response_timeout_seconds'],
      values: {
        wait_for_response: false,
        response_timeout_seconds: 30,
      },
    }
  },
  validations() {
    return {
      values: {
        response_timeout_seconds: {
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 1 }),
            minValue(1)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 120 }),
            maxValue(120)
          ),
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
        },
      },
    }
  },
}
</script>

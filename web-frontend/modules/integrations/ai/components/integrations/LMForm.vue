<template>
  <div>
    <FormGroup
      :label="$t('lmForm.model')"
      required
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('model')"
    >
      <FormInput
        v-model="v$.values.model.$model"
        :placeholder="$t('lmForm.modelPlaceholder')"
        @blur="v$.values.model.$touch()"
      />
    </FormGroup>

    <FormGroup
      :label="$t('lmForm.apiKey')"
      required
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('api_key')"
    >
      <FormInput
        v-model="v$.values.api_key.$model"
        :placeholder="$t('lmForm.apiKeyPlaceholder')"
        @blur="v$.values.api_key.$touch()"
      />
    </FormGroup>

    <FormGroup
      :label="$t('lmForm.apiBaseUrl')"
      small-label
      class="margin-bottom-2"
    >
      <FormInput
        v-model="v$.values.api_base_url.$model"
        :placeholder="$t('lmForm.apiBaseUrlPlaceholder')"
        @blur="v$.values.api_base_url.$touch()"
      />
    </FormGroup>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { required } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'

export default {
  name: 'LMForm',
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        model: '',
        api_key: '',
        api_base_url: '',
      },
      allowedValues: ['model', 'api_key', 'api_base_url'],
    }
  },
  validations() {
    return {
      values: {
        model: { required },
        api_key: { required },
        api_base_url: {},
      },
    }
  },
}
</script>

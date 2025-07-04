<template>
  <div>
    <FormGroup
      :label="$t('smtpForm.host')"
      required
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('host')"
    >
      <FormInput
        v-model="v$.values.host.$model"
        :placeholder="$t('smtpForm.hostPlaceholder')"
        @blur="v$.values.host.$touch()"
      />
    </FormGroup>

    <FormGroup
      :label="$t('smtpForm.port')"
      required
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('port')"
    >
      <FormInput
        v-model="v$.values.port.$model"
        type="number"
        :placeholder="$t('smtpForm.portPlaceholder')"
        :to-value="(value) => parseInt(value)"
        @blur="v$.values.port.$touch()"
      />
    </FormGroup>

    <FormGroup
      :label="$t('smtpForm.useTls')"
      small-label
      class="margin-bottom-2"
    >
      <Checkbox v-model="values.use_tls" />
    </FormGroup>

    <FormGroup
      :label="$t('smtpForm.username')"
      small-label
      class="margin-bottom-2"
    >
      <FormInput
        v-model="values.username"
        :placeholder="$t('smtpForm.usernamePlaceholder')"
      />
    </FormGroup>

    <FormGroup :label="$t('smtpForm.password')" small-label>
      <FormInput
        v-model="values.password"
        type="password"
        :placeholder="$t('smtpForm.passwordPlaceholder')"
      />
    </FormGroup>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { required, integer, minValue, maxValue } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'

export default {
  name: 'SMTPForm',
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
        host: '',
        port: 587,
        use_tls: true,
        username: '',
        password: '',
      },
      allowedValues: ['host', 'port', 'use_tls', 'username', 'password'],
    }
  },
  validations() {
    return {
      values: {
        host: { required },
        port: {
          required,
          integer,
          minValue: minValue(1),
          maxValue: maxValue(65535),
        },
        use_tls: {},
        username: {},
        password: {},
      },
    }
  },
}
</script>

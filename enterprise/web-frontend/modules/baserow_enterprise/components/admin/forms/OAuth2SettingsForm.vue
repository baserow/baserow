<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('oauthSettingsForm.providerName')"
      :error="fieldHasErrors('name')"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        size="large"
        :error="fieldHasErrors('name')"
        :placeholder="$t('oauthSettingsForm.providerNamePlaceholder')"
        @blur="v$.values.name.$touch"
      ></FormInput>

      <template #error>
        {{ v$.values.name.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('client_id')"
      small-label
      :label="$t('oauthSettingsForm.clientId')"
      required
      class="margin-bottom-2"
    >
      <FormInput
        ref="client_id"
        v-model="v$.values.client_id.$model"
        size="large"
        :error="fieldHasErrors('client_id')"
        :placeholder="$t('oauthSettingsForm.clientIdPlaceholder')"
        @blur="v$.values.client_id.$touch"
      ></FormInput>

      <template #error>
        {{ v$.values.client_id.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('oauthSettingsForm.secret')"
      :error="fieldHasErrors('secret')"
      class="margin-bottom-2"
      required
    >
      <FormInput
        ref="secret"
        v-model="v$.values.secret.$model"
        size="large"
        :error="fieldHasErrors('secret')"
        :placeholder="$t('oauthSettingsForm.secretPlaceholder')"
        @blur="v$.values.secret.$touch"
      ></FormInput>

      <template #error>
        {{ v$.values.secret.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      :label="$t('oauthSettingsForm.callbackUrl')"
      small-label
      required
    >
      <code>{{ callbackUrl }}</code>
    </FormGroup>
    <slot></slot>
  </form>
</template>

<script>
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'

export default {
  name: 'OAuth2SettingsForm',
  mixins: [authProviderForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['name', 'client_id', 'secret'],
      values: {
        name: '',
        client_id: '',
        secret: '',
      },
    }
  },
  computed: {
    callbackUrl() {
      return this.authProviderType.getCallbackUrl(this.authProvider)
    },
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        client_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        secret: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>

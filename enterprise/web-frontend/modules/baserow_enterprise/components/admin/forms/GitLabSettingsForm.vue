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
      small-label
      :label="$t('oauthSettingsForm.baseUrl')"
      :error="fieldHasErrors('base_url')"
      class="margin-bottom-2"
      required
    >
      <FormInput
        ref="base_url"
        v-model="v$.values.base_url.$model"
        size="large"
        :error="fieldHasErrors('base_url')"
        :placeholder="$t('oauthSettingsForm.baseUrlPlaceholder')"
        @blur="v$.values.base_url.$touch"
      ></FormInput>

      <template #error>
        {{ v$.values.base_url.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.values.client_id.$error"
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
        :placeholder="$t('oauthSettingsForm.secretPlaceholder')"
        :error="fieldHasErrors('secret')"
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
import { useVuelidate } from '@vuelidate/core'
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import { required, url, helpers } from '@vuelidate/validators'

export default {
  name: 'GitLabSettingsForm',
  mixins: [authProviderForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['name', 'base_url', 'client_id', 'secret'],
      values: {
        name: '',
        base_url: 'https://gitlab.com',
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
        base_url: {
          url: helpers.withMessage(
            this.$t('oauthSettingsForm.invalidBaseUrl'),
            url
          ),
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

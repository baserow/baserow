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
      :error="fieldHasErrors('base_url') || !!serverErrors.base_url"
      class="margin-bottom-2"
      required
    >
      <FormInput
        ref="base_url"
        v-model="v$.values.base_url.$model"
        size="large"
        :error="fieldHasErrors('base_url') || !!serverErrors.base_url"
        :placeholder="$t('oauthSettingsForm.baseUrlPlaceholder')"
        @blur="v$.values.base_url.$touch"
        @input="serverErrors.base_url = null"
      ></FormInput>

      <template #error>
        <div v-if="v$.values.base_url.required.$invalid">
          {{ $t('error.requiredField') }}
        </div>
        <div v-else-if="v$.values.base_url.url.$invalid">
          {{ $t('oauthSettingsForm.invalidBaseUrl') }}
        </div>
        <div v-else-if="serverErrors.base_url?.code === 'duplicate_url'">
          {{ $t('oauthSettingsForm.duplicateBaseUrl') }}
        </div>
        <div v-else-if="serverErrors.base_url?.code === 'invalid_url'">
          {{ $t('oauthSettingsForm.invalidBaseUrl') }}
        </div>
        <div v-else-if="!!serverErrors.base_url">
          {{ $t('oauthSettingsForm.invalidBaseUrl') }}
        </div>
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
    <slot name="config">
      <FormGroup
        small-label
        :label="$t('oauthSettingsForm.callbackUrl')"
        required
      >
        <code>{{ callbackUrl }}</code>
      </FormGroup>
    </slot>
    <slot></slot>
  </form>
</template>

<script>
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import { useVuelidate } from '@vuelidate/core'
import { required, url, helpers } from '@vuelidate/validators'

export default {
  name: 'OpenIdConnectSettingsForm',
  mixins: [authProviderForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['name', 'base_url', 'client_id', 'secret'],
      values: {
        name: '',
        base_url: '',
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
          required,
          url,
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

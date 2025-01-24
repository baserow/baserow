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
        v-model="values.name"
        size="large"
        :error="fieldHasErrors('name')"
        :placeholder="$t('oauthSettingsForm.providerNamePlaceholder')"
        @blur="$v.values.name.$touch()"
      ></FormInput>

      <template v-if="$v.values.name.$dirty && !$v.values.name.required" #error>
        {{ $t('error.requiredField') }}</template
      >
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
        v-model="values.client_id"
        size="large"
        :error="fieldHasErrors('client_id')"
        :placeholder="$t('oauthSettingsForm.clientIdPlaceholder')"
        @blur="$v.values.client_id.$touch()"
      ></FormInput>

      <template
        v-if="$v.values.client_id.$dirty && !$v.values.client_id.required"
        #error
      >
        {{ $t('error.requiredField') }}
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
        v-model="values.secret"
        size="large"
        :error="fieldHasErrors('secret')"
        :placeholder="$t('oauthSettingsForm.secretPlaceholder')"
        @blur="$v.values.secret.$touch()"
      ></FormInput>

      <template #error>
        <span v-if="$v.values.secret.$dirty && !$v.values.secret.required">
          {{ $t('error.requiredField') }}
        </span>
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
import { required } from 'vuelidate/lib/validators'
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'

export default {
  name: 'OAuth2SettingsForm',
  mixins: [authProviderForm],
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
        name: { required },
        client_id: { required },
        secret: { required },
      },
    }
  },
}
</script>

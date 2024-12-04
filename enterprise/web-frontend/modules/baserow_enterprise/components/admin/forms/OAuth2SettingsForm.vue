<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('oauthSettingsForm.providerName')"
      :error="v$.name.$error"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.name.$model"
        size="large"
        :error="v$.name.$error"
        :placeholder="$t('oauthSettingsForm.providerNamePlaceholder')"
        @blur="v$.name.$touch"
      ></FormInput>

      <template #error v-if="v$.name.required.$invalid">
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.client_id.required.$error"
      small-label
      :label="$t('oauthSettingsForm.clientId')"
      required
      class="margin-bottom-2"
    >
      <FormInput
        ref="client_id"
        v-model="v$.client_id.$model"
        size="large"
        :error="v$.client_id.required.$error"
        :placeholder="$t('oauthSettingsForm.clientIdPlaceholder')"
        @blur="v$.client_id.$touch"
      ></FormInput>

      <template #error v-if="v$.client_id.required.$invalid">
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('oauthSettingsForm.secret')"
      :error="v$.secret.required.$error"
      class="margin-bottom-2"
      required
    >
      <FormInput
        ref="secret"
        v-model="v$.secret.$model"
        size="large"
        :error="v$.secret.$error"
        :placeholder="$t('oauthSettingsForm.secretPlaceholder')"
        @blur="v$.secret.$touch"
      ></FormInput>

      <template #error>
        <span v-if="v$.secret.required.$invalid">
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
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'OAuth2SettingsForm',
  mixins: [form],
  props: {
    authProvider: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    authProviderType: {
      type: String,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      allowedValues: ['name', 'client_id', 'secret'],
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      name: this.providerName,
      client_id: this.authProvider.client_id || '',
      secret: this.authProvider.secret || '',
    })

    const rules = computed(() => ({
      name: { required },
      client_id: { required },
      secret: { required },
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  computed: {
    providerName() {
      const type = this.authProviderType
        ? this.authProviderType
        : this.authProvider.type
      return this.$registry
        .get('authProvider', type)
        .getProviderName(this.authProvider)
    },
    callbackUrl() {
      if (!this.authProvider.id) {
        const nextProviderId =
          this.$store.getters['authProviderAdmin/getNextProviderId']
        return `${this.$config.PUBLIC_BACKEND_URL}/api/sso/oauth2/callback/${nextProviderId}/`
      }
      return `${this.$config.PUBLIC_BACKEND_URL}/api/sso/oauth2/callback/${this.authProvider.id}/`
    },
  },
  methods: {
    getDefaultValues() {
      return {
        name: this.providerName,
        client_id: this.authProvider.client_id || '',
        secret: this.authProvider.secret || '',
      }
    },
    submit() {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }
      this.$emit('submit', this.values)
    },
  },
}
</script>

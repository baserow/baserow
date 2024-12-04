<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :error="v$.domain.$error"
      class="margin-bottom-2"
    >
      <template #label>
        {{ $t('samlSettingsForm.domain') }}
        <img
          v-if="authProvider && authProvider.is_verified"
          class="control__label-right-icon"
          :alt="$t('samlSettingsForm.providerIsVerified')"
          :title="$t('samlSettingsForm.providerIsVerified')"
          :src="getVerifiedIcon()"
        />
      </template>

      <FormInput
        ref="domain"
        v-model="v$.domain.$model"
        size="large"
        :error="v$.domain.$error || serverErrors.domain"
        :placeholder="$t('samlSettingsForm.domainPlaceholder')"
        @input="serverErrors.domain = null"
        @blur="v$.domain.$touch"
      ></FormInput>
      <template #error>
        <span v-if="v$.domain.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>

        <span v-else-if="v$.domain.mustHaveUniqueDomain.$invalid">
          {{ $t('samlSettingsForm.domainAlreadyExists') }}
        </span>

        <span v-else-if="serverErrors.domain">
          {{ $t('samlSettingsForm.invalidDomain') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      required
      :label="$t('samlSettingsForm.metadata')"
      :error="v$.metadata.$error"
      class="margin-bottom-2"
    >
      <FormTextarea
        ref="metadata"
        v-model="v$.metadata.$model"
        :rows="12"
        :error="v$.metadata.$error || serverErrors.metadata"
        :placeholder="$t('samlSettingsForm.metadataPlaceholder')"
        @input="serverErrors.metadata = null"
        @blur="v$.metadata.$touch"
      ></FormTextarea>

      <template #error>
        <span v-if="v$.metadata.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="serverErrors.metadata">
          {{ $t('samlSettingsForm.invalidMetadata') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      required
      :label="$t('samlSettingsForm.relayStateUrl')"
      class="margin-bottom-2"
    >
      <code>{{ getRelayStateUrl() }}</code>
    </FormGroup>

    <FormGroup
      small-label
      required
      :label="$t('samlSettingsForm.acsUrl')"
      class="margin-bottom-2"
    >
      <code>{{ getAcsUrl() }}</code>
    </FormGroup>

    <Expandable card class="margin-bottom-2">
      <template #header="{ toggle, expanded }">
        <div class="flex flex-100 justify-content-space-between">
          <div>
            <div>
              <a @click="toggle">
                {{ $t('samlSettingsForm.samlResponseSettings') }}
                <i
                  :class="
                    expanded
                      ? 'iconoir-nav-arrow-down'
                      : 'iconoir-nav-arrow-right'
                  "
                ></i>
              </a>
            </div>
          </div>
          <div>
            {{
              usingDefaultAttrs()
                ? $t('samlSettingsForm.defaultAttrs')
                : $t('samlSettingsForm.customAttrs')
            }}
          </div>
        </div>
      </template>
      <template #default>
        <FormGroup
          small-label
          required
          :error="fieldHasErrors('email_attr_key')"
          :label="$t('samlSettingsForm.emailAttrKey')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="email_attr_key"
            v-model="values.email_attr_key"
            :error="fieldHasErrors('email_attr_key')"
            :placeholder="defaultAttrs.email_attr_key"
            @blur="$v.values.email_attr_key.$touch()"
          ></FormInput>
          <template #helper>
            {{ $t('samlSettingsForm.emailAttrKeyHelper') }}
          </template>
          <template #error>
            <span v-if="v$.email_attr_key.required.$invalid">
              {{ $t('error.requiredField') }}
            </span>
            <span v-else-if="v$.email_attr_key.maxLength.$invalid">
              {{ $t('error.maxLength', { max: 32 }) }}
            </span>
            <span v-else-if="v$.email_attr_key.invalid.$invalid">
              {{ $t('error.invalidCharacters') }}
            </span>
          </template>
        </FormGroup>

        <FormGroup
          small-label
          required
          :error="v$.first_name_attr_key.$error"
          :label="$t('samlSettingsForm.firstNameAttrKey')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="firstNameAttrKey"
            v-model="v$.first_name_attr_key.$model"
            :error="v$.first_name_attr_key.$error"
            :placeholder="defaultAttrs.first_name_attr_key"
            @blur="v$.first_name_attr_key.$touch"
          ></FormInput>
          <template #helper>
            {{ $t('samlSettingsForm.firstNameAttrKeyHelper') }}
          </template>

          <template #error>
            <span v-if="v$.first_name_attr_key.required.$invalid">
              {{ $t('error.requiredField') }}
            </span>
            <span v-else-if="v$.first_name_attr_key.maxLength.$invalid">
              {{ $t('error.maxLength', { max: 32 }) }}
            </span>
            <span v-else-if="v$.first_name_attr_key.invalid.$invalid">
              {{ $t('error.invalidCharacters') }}
            </span>
          </template>
        </FormGroup>

        <FormGroup
          small-label
          required
          :error="v$.last_name_attr_key.$error"
          :label="$t('samlSettingsForm.lastNameAttrKey')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="lastNameAttrKey"
            v-model="v$.last_name_attr_key.$model"
            :error="v$.last_name_attr_key.$error"
            :placeholder="defaultAttrs.last_name_attr_key"
            @blur="v$.last_name_attr_key.$touch"
          ></FormInput>
          <template #helper>
            {{ $t('samlSettingsForm.lastNameAttrKeyHelper') }}
          </template>
          <template #error>
            <span v-if="v$.last_name_attr_key.maxLength.$invalid">
              {{ $t('error.maxLength', { max: 32 }) }}
            </span>
            <span v-else-if="v$.last_name_attr_key.invalid.$invalid">
              {{ $t('error.invalidCharacters') }}
            </span>
          </template>
        </FormGroup>
      </template>
    </Expandable>

    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required, maxLength, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

const alphanumericDotDashUnderscore = helpers.regex(/^[a-zA-Z0-9._-]*$/)

export default {
  name: 'SamlSettingsForm',
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
      allowedValues: ['domain', 'metadata'],
      serverErrors: {},
      values: null,
      v$: null,
      values: null,
    }
  },
  computed: {
    samlDomains() {
      const samlAuthProviders =
        this.$store.getters['authProviderAdmin/getAll'].saml?.authProviders ||
        []
      return samlAuthProviders
        .filter(
          (authProvider) => authProvider.domain !== this.authProvider.domain
        )
        .map((authProvider) => authProvider.domain)
    },
    defaultAttrs() {
      return {
        email_attr_key: 'user.email',
        first_name_attr_key: 'user.first_name',
        last_name_attr_key: 'user.last_name',
      }
    },
    type() {
      return this.authProviderType || this.authProvider.type
    },
  },
  created() {
    const values = reactive({
      domain: '',
      metadata: '',
      email_attr_key: '',
      first_name_attr_key: '',
      last_name_attr_key: '',
    })

    const rules = computed(() => ({
      domain: { required, mustHaveUniqueDomain: this.mustHaveUniqueDomain },
      metadata: { required },
      email_attr_key: {
        required,
        maxLength: maxLength(32),
        invalid: alphanumericDotDashUnderscore,
      },
      first_name_attr_key: {
        required,
        maxLength: maxLength(32),
        invalid: alphanumericDotDashUnderscore,
      },
      last_name_attr_key: {
        maxLength: maxLength(32),
        invalid: alphanumericDotDashUnderscore,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    usingDefaultAttrs() {
      return (
        this.values.email_attr_key === this.defaultAttrs.email_attr_key &&
        this.values.first_name_attr_key ===
          this.defaultAttrs.first_name_attr_key &&
        this.values.last_name_attr_key === this.defaultAttrs.last_name_attr_key
      )
    },
    getDefaultValues() {
      const authProviderAttrs = {
        email_attr_key: this.authProvider.email_attr_key,
        first_name_attr_key: this.authProvider.first_name_attr_key,
        last_name_attr_key: this.authProvider.last_name_attr_key,
      }
      const samlAttrs = this.authProvider.id
        ? authProviderAttrs
        : this.defaultAttrs
      return {
        domain: this.authProvider.domain || '',
        metadata: this.authProvider.metadata || '',
        ...samlAttrs,
      }
    },
    getFieldErrorMsg(fieldName) {
      if (!this.v$.values[fieldName].$dirty) {
        return ''
      } else if (!this.$v.values[fieldName].maxLength) {
        return this.$t('error.maxLength', {
          max: this.v$.values[fieldName].$params.maxLength.max,
        })
      } else if (!this.$v.values[fieldName].invalid) {
        return this.$t('error.invalidCharacters')
      } else if (this.$v.values[fieldName].required === false) {
        return this.$t('error.requiredField')
      }
    },
    getRelayStateUrl() {
      return this.$store.getters['authProviderAdmin/getType'](this.type)
        .relayStateUrl
    },
    getAcsUrl() {
      return this.$store.getters['authProviderAdmin/getType'](this.type).acsUrl
    },
    getVerifiedIcon() {
      return this.$registry.get('authProvider', this.type).getVerifiedIcon()
    },
    submit() {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }
      this.$emit('submit', this.values)
    },
    mustHaveUniqueDomain(domain) {
      return !this.samlDomains.includes(domain.trim())
    },
    handleServerError(error) {
      if (error.handler.code !== 'ERROR_REQUEST_BODY_VALIDATION') return false

      for (const [key, value] of Object.entries(error.handler.detail || {})) {
        this.serverErrors[key] = value
      }
      return true
    },
  },
}
</script>

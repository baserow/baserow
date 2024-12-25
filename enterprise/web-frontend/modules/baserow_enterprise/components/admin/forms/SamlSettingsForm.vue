<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :error="fieldHasErrors('domain')"
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
        v-model="values.domain"
        size="large"
        :error="fieldHasErrors('domain') || !!serverErrors.domain"
        :placeholder="$t('samlSettingsForm.domainPlaceholder')"
        @input="onDomainInput()"
        @blur="$v.values.domain.$touch()"
      ></FormInput>
      <template #error>
        <span v-if="$v.values.domain.$dirty && !$v.values.domain.required">
          {{ $t('error.requiredField') }}
        </span>

        <span
          v-else-if="
            $v.values.domain.$dirty && !$v.values.domain.mustHaveUniqueDomain
          "
          class="error"
        >
          {{ $t('samlSettingsForm.domainAlreadyExists') }}
        </span>

        <span v-else-if="serverErrors.domain" class="error">
          {{ $t('samlSettingsForm.invalidDomain') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      required
      :label="$t('samlSettingsForm.metadata')"
      :error="fieldHasErrors('metadata') || !!serverErrors.metadata"
      class="margin-bottom-2"
    >
      <FormTextarea
        ref="metadata"
        v-model="values.metadata"
        :rows="8"
        :error="fieldHasErrors('metadata') || !!serverErrors.metadata"
        :placeholder="$t('samlSettingsForm.metadataPlaceholder')"
        @input="onMetadataInput()"
        @blur="$v.values.metadata.$touch()"
      ></FormTextarea>

      <template #error>
        <span v-if="$v.values.metadata.$dirty && !$v.values.metadata.required">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="serverErrors.metadata">
          {{ $t('samlSettingsForm.invalidMetadata') }}
        </span>
      </template>
    </FormGroup>

    <slot name="config">
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
    </slot>

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
              usingDefaultAttrs
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
          <template #error>{{ getFieldErrorMsg('email_attr_key') }}</template>
        </FormGroup>

        <FormGroup
          small-label
          required
          :error="fieldHasErrors('first_name_attr_key')"
          :label="$t('samlSettingsForm.firstNameAttrKey')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="firstNameAttrKey"
            v-model="values.first_name_attr_key"
            :error="fieldHasErrors('first_name_attr_key')"
            :placeholder="defaultAttrs.first_name_attr_key"
            @blur="$v.values.first_name_attr_key.$touch()"
          ></FormInput>
          <template #helper>
            {{ $t('samlSettingsForm.firstNameAttrKeyHelper') }}
          </template>
          <template #error>{{
            getFieldErrorMsg('first_name_attr_key')
          }}</template>
        </FormGroup>

        <FormGroup
          small-label
          required
          :error="fieldHasErrors('last_name_attr_key')"
          :label="$t('samlSettingsForm.lastNameAttrKey')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="lastNameAttrKey"
            v-model="values.last_name_attr_key"
            :error="fieldHasErrors('last_name_attr_key')"
            :placeholder="defaultAttrs.last_name_attr_key"
            @blur="$v.values.last_name_attr_key.$touch()"
          ></FormInput>
          <template #helper>
            {{ $t('samlSettingsForm.lastNameAttrKeyHelper') }}
          </template>
          <template #error>{{
            getFieldErrorMsg('last_name_attr_key')
          }}</template>
        </FormGroup>
      </template>
    </Expandable>

    <slot></slot>
  </form>
</template>

<script>
import { maxLength, required, helpers } from 'vuelidate/lib/validators'
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'

const alphanumericDotDashUnderscore = helpers.regex(
  'alphanumericDotDashUnderscore',
  /^[a-zA-Z0-9._-]*$/
)

export default {
  name: 'SamlSettingsForm',
  mixins: [authProviderForm],
  data() {
    return {
      allowedValues: [
        'domain',
        'metadata',
        'email_attr_key',
        'first_name_attr_key',
        'last_name_attr_key',
      ],
      values: {
        domain: '',
        metadata: '',
        email_attr_key: 'user.email',
        first_name_attr_key: 'user.first_name',
        last_name_attr_key: 'user.last_name',
      },
    }
  },
  computed: {
    allSamlProviders() {
      return this.authProviders.saml || []
    },
    samlDomains() {
      return this.allSamlProviders
        .filter((authProvider) => authProvider.id !== this.authProvider.id)
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
      return this.authProviderType.getType()
    },
    usingDefaultAttrs() {
      return (
        this.values.email_attr_key === this.defaultAttrs.email_attr_key &&
        this.values.first_name_attr_key ===
          this.defaultAttrs.first_name_attr_key &&
        this.values.last_name_attr_key === this.defaultAttrs.last_name_attr_key
      )
    },
  },
  methods: {
    onDomainInput() {
      this.serverErrors.domain = null
    },
    onMetadataInput() {
      this.serverErrors.metadata = null
    },
    getFieldErrorMsg(fieldName) {
      if (!this.$v.values[fieldName].$dirty) {
        return ''
      } else if (!this.$v.values[fieldName].maxLength) {
        return this.$t('error.maxLength', {
          max: this.$v.values[fieldName].$params.maxLength.max,
        })
      } else if (!this.$v.values[fieldName].invalid) {
        return this.$t('error.invalidCharacters')
      } else if (this.$v.values[fieldName].required === false) {
        return this.$t('error.requiredField')
      }
    },
    getRelayStateUrl() {
      return this.authProviderType.getRelayStateUrl()
    },
    getAcsUrl() {
      return this.authProviderType.getAcsUrl()
    },
    getVerifiedIcon() {
      return this.authProviderType.getVerifiedIcon()
    },
    mustHaveUniqueDomain(domain) {
      return !this.samlDomains.includes(domain.trim())
    },
  },
  validations() {
    return {
      values: {
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
      },
    }
  },
}
</script>

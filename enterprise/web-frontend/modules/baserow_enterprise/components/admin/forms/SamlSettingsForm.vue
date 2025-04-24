<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :error="fieldHasErrors('domain') || !!serverErrors.domain"
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
        v-model="v$.values.domain.$model"
        size="large"
        :error="fieldHasErrors('domain') || !!serverErrors.domain"
        :placeholder="$t('samlSettingsForm.domainPlaceholder')"
        @input="onDomainInput()"
        @blur="v$.values.domain.$touch"
      ></FormInput>
      <template #error>
        {{
          v$.values.domain.$errors[0]?.$message || serverErrors.domain[0].error
        }}
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
        v-model="v$.values.metadata.$model"
        :rows="12"
        :error="fieldHasErrors('metadata') || !!serverErrors.metadata"
        :placeholder="$t('samlSettingsForm.metadataPlaceholder')"
        @input="onMetadataInput()"
        @blur="v$.values.metadata.$touch"
      ></FormTextarea>

      <template #error>
        {{
          v$.values.metadata.$errors[0]?.$message ||
          serverErrors.metadata[0].error
        }}
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
            v-model="v$.values.email_attr_key.$model"
            :error="fieldHasErrors('email_attr_key')"
            :placeholder="defaultAttrs.email_attr_key"
            @blur="v$.values.email_attr_key.$touch"
          ></FormInput>
          <template #helper>
            {{ $t('samlSettingsForm.emailAttrKeyHelper') }}
          </template>
          <template #error>
            {{ v$.values.email_attr_key.$errors[0]?.$message }}
          </template>
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
            v-model="v$.values.first_name_attr_key.$model"
            :error="fieldHasErrors('first_name_attr_key')"
            :placeholder="defaultAttrs.first_name_attr_key"
            @blur="v$.values.first_name_attr_key.$touch"
          ></FormInput>
          <template #helper>
            {{ $t('samlSettingsForm.firstNameAttrKeyHelper') }}
          </template>

          <template #error>
            {{ v$.values.first_name_attr_key.$errors[0]?.$message }}
          </template>
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
            v-model="v$.values.last_name_attr_key.$model"
            :error="fieldHasErrors('last_name_attr_key')"
            :placeholder="defaultAttrs.last_name_attr_key"
          ></FormInput>
          <template #helper>
            {{ $t('samlSettingsForm.lastNameAttrKeyHelper') }}
          </template>
          <template #error>
            {{ v$.values.last_name_attr_key.$errors[0]?.$message }}
          </template>
        </FormGroup>
      </template>
    </Expandable>

    <slot></slot>
  </form>
</template>

<script>
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import { useVuelidate } from '@vuelidate/core'
import { required, maxLength, helpers } from '@vuelidate/validators'

const alphanumericDotDashUnderscore = helpers.regex(/^[a-zA-Z0-9._-]*$/)

export default {
  name: 'SamlSettingsForm',
  mixins: [authProviderForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'domain',
        'metadata',
        'email_attr_key',
        'first_name_attr_key',
        'last_name_attr_key',
      ],
      serverErrors: {},
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
        domain: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          mustHaveUniqueDomain: helpers.withMessage(
            this.$t('samlSettingsForm.domainAlreadyExists'),
            this.mustHaveUniqueDomain
          ),
        },
        metadata: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        email_attr_key: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 32 }),
            maxLength(32)
          ),
          invalid: helpers.withMessage(
            this.$t('error.invalidCharacters'),
            alphanumericDotDashUnderscore
          ),
        },
        first_name_attr_key: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 32 }),
            maxLength(32)
          ),
          invalid: helpers.withMessage(
            this.$t('error.invalidCharacters'),
            alphanumericDotDashUnderscore
          ),
        },
        last_name_attr_key: {
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 32 }),
            maxLength(32)
          ),
          invalid: helpers.withMessage(
            this.$t('error.invalidCharacters'),
            alphanumericDotDashUnderscore
          ),
        },
      },
    }
  },
}
</script>

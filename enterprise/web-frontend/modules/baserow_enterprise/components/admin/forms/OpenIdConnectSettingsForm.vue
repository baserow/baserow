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

    <FormGroup
      :label="$t('oauthSettingsForm.useIdToken')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="v$.values.use_id_token.$model"></Checkbox>
    </FormGroup>

    <Expandable card class="margin-bottom-2">
      <template #header="{ toggle, expanded }">
        <div class="flex flex-100 justify-content-space-between">
          <div>
            <div>
              <a @click="toggle">
                {{ $t('oauthSettingsForm.responseSettings') }}
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
                ? $t('oauthSettingsForm.defaultAttrs')
                : $t('oauthSettingsForm.customAttrs')
            }}
          </div>
        </div>
      </template>
      <template #default>
        <FormGroup
          small-label
          required
          :error="fieldHasErrors('email_attr_key')"
          :label="$t('oauthSettingsForm.emailAttrKey')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="email_attr_key"
            v-model="v$.values.email_attr_key.$model"
            :error="fieldHasErrors('email_attr_key')"
            :placeholder="defaultAttrs.email_attr_key"
          ></FormInput>
          <template #helper>
            {{ $t('oauthSettingsForm.emailAttrKeyHelper') }}
          </template>
          <template #error>
            {{ v$.values.email_attr_key.$errors[0]?.$message }}
          </template>
        </FormGroup>
        <FormGroup
          small-label
          required
          :error="fieldHasErrors('first_name_attr_key')"
          :label="$t('oauthSettingsForm.firstNameAttrKey')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="firstNameAttrKey"
            v-model="v$.values.first_name_attr_key.$model"
            :error="fieldHasErrors('first_name_attr_key')"
            :placeholder="defaultAttrs.first_name_attr_key"
          ></FormInput>
          <template #helper>
            {{ $t('oauthSettingsForm.firstNameAttrKeyHelper') }}
          </template>

          <template #error>
            {{ v$.values.first_name_attr_key.$errors[0]?.$message }}
          </template>
        </FormGroup>
        <FormGroup
          small-label
          required
          :error="fieldHasErrors('last_name_attr_key')"
          :label="$t('oauthSettingsForm.lastNameAttrKey')"
          class="margin-bottom-2"
        >
          <FormInput
            ref="lastNameAttrKey"
            v-model="v$.values.last_name_attr_key.$model"
            :error="fieldHasErrors('last_name_attr_key')"
            :placeholder="defaultAttrs.last_name_attr_key"
          ></FormInput>
          <template #helper>
            {{ $t('oauthSettingsForm.lastNameAttrKeyHelper') }}
          </template>

          <template #error>
            {{ v$.values.last_name_attr_key.$errors[0]?.$message }}
          </template>
        </FormGroup>
      </template>
    </Expandable>
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
import { required, url, helpers, maxLength } from '@vuelidate/validators'

const alphanumericDotDashUnderscore = helpers.regex(/^[a-zA-Z0-9._-]*$/)

export default {
  name: 'OpenIdConnectSettingsForm',
  mixins: [authProviderForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'name',
        'base_url',
        'client_id',
        'secret',
        'email_attr_key',
        'first_name_attr_key',
        'last_name_attr_key',
        'use_id_token',
      ],
      values: {
        name: '',
        base_url: '',
        client_id: '',
        secret: '',
        email_attr_key: 'email',
        first_name_attr_key: 'name',
        last_name_attr_key: '',
        use_id_token: false,
      },
    }
  },
  computed: {
    callbackUrl() {
      return this.authProviderType.getCallbackUrl(this.authProvider)
    },
    defaultAttrs() {
      return {
        email_attr_key: 'email',
        last_name_attr_key: '',
        first_name_attr_key: 'name',
      }
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
        use_id_token: {},
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

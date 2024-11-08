<template>
  <form @submit.prevent="submit">
    <FormRow>
      <FormGroup
        :label="$t('updateUserSourceForm.nameFieldLabel')"
        required
        small-label
        :error-message="getError('name')"
      >
        <FormInput
          v-model="$v.values.name.$model"
          size="large"
          class="update-user-source-form__name-input"
          :placeholder="$t('updateUserSourceForm.nameFieldPlaceholder')"
        />
      </FormGroup>
      <FormGroup
        :label="$t('updateUserSourceForm.integrationFieldLabel')"
        :error-message="getError('integration_id')"
        required
        small-label
      >
        <IntegrationDropdown
          v-model="$v.values.integration_id.$model"
          :application="builder"
          :integrations="integrations"
          :integration-type="userSourceType.integrationType"
          size="large"
        />
      </FormGroup>
    </FormRow>

    <component
      :is="userSourceType.formComponent"
      v-if="integration"
      :default-values="defaultValues"
      :application="builder"
      :integration="integration"
      @values-changed="emitChange"
    />
    <div v-if="integration">
      <FormGroup
        :label="$t('updateUserSourceForm.authTitle')"
        small-label
        required
      >
        <div
          v-for="appAuthType in appAuthProviderTypes"
          :key="appAuthType.type"
        >
          <Checkbox
            :checked="hasAtLeastOneOfThisType(appAuthType)"
            @input="onSelect(appAuthType)"
          >
            {{ appAuthType.name }}
          </Checkbox>

          <div
            v-for="appAuthProvider in appAuthProviderPerTypes[appAuthType.type]"
            :key="appAuthProvider.id"
            class="update-user-source-form__auth-provider-form"
          >
            <component
              :is="appAuthType.formComponent"
              v-if="hasAtLeastOneOfThisType(appAuthType)"
              :integration="integration"
              :current-user-source="fullValues"
              :auth-providers="[]"
              :auth-provider="appAuthProvider"
              :default-values="appAuthProvider"
              :auth-provider-type="appAuthType"
              excluded-form
              @values-changed="updateAuthProvider(appAuthProvider, $event)"
            />
          </div>
        </div>
      </FormGroup>

      <input type="submit" hidden />
    </div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import { required, maxLength } from 'vuelidate/lib/validators'
import { uuid } from '@baserow/modules/core/utils/string'

export default {
  components: { IntegrationDropdown },
  mixins: [form],
  props: {
    builder: {
      type: Object,
      required: true,
    },
    userSourceType: {
      type: Object,
      required: false,
      default: null,
    },
    integrations: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      values: {
        integration_id: null,
        name: '',
        auth_providers: [],
      },
      fullValues: this.getFormValues(),
    }
  },
  computed: {
    integration() {
      if (!this.values.integration_id) {
        return null
      }
      return this.integrations.find(
        ({ id }) => id === this.values.integration_id
      )
    },
    appAuthProviderTypes() {
      return this.$registry.getOrderedList('appAuthProvider')
    },
    appAuthProviderPerTypes() {
      return Object.fromEntries(
        this.appAuthProviderTypes.map((authType) => {
          return [
            authType.type,
            this.values.auth_providers.filter(
              ({ type }) => type === authType.type
            ),
          ]
        })
      )
    },
  },
  methods: {
    // Override the default getChildFormValues to exclude the provider forms from
    // final values as they are handled directly by this component
    getChildFormsValues() {
      return Object.assign(
        {},
        ...this.$children
          .filter(
            (child) =>
              'getChildFormsValues' in child &&
              child.$attrs['excluded-form'] === undefined
          )
          .map((child) => {
            return child.getFormValues()
          })
      )
    },
    hasAtLeastOneOfThisType(appAuthProviderType) {
      return this.appAuthProviderPerTypes[appAuthProviderType.type]?.length > 0
    },
    onSelect(appAuthProviderType) {
      if (this.hasAtLeastOneOfThisType(appAuthProviderType)) {
        this.values.auth_providers = this.values.auth_providers.filter(
          ({ type }) => type !== appAuthProviderType.type
        )
      } else {
        this.values.auth_providers.push({
          type: appAuthProviderType.type,
          id: uuid(),
        })
      }
    },
    updateAuthProvider(authProviderToChange, values) {
      this.values.auth_providers = this.values.auth_providers.map(
        (authProvider) => {
          if (authProvider.id === authProviderToChange.id) {
            return { ...authProvider, ...values }
          }
          return authProvider
        }
      )
    },
    emitChange() {
      this.fullValues = this.getFormValues()
    },
    getError(fieldName) {
      if (!this.$v.values[fieldName].$dirty) {
        return ''
      }
      const fieldState = this.$v.values[fieldName]
      if (!fieldState.required) {
        return this.$t('error.requiredField')
      }
      if (fieldName === 'name' && !fieldState.maxLength) {
        return this.$t('error.maxLength', { max: 255 })
      }
      return ''
    },
  },
  validations: {
    values: {
      integration_id: {
        required,
      },
      name: {
        required,
        maxLength: maxLength(255),
      },
    },
  },
}
</script>

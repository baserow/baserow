<template>
  <form @submit.prevent="submit">
    <FormRow class="margin-bottom-2">
      <FormGroup
        :label="$t('updateUserSourceForm.nameFieldLabel')"
        :error-message="getFirstErrorMessage('name')"
        required
        small-label
      >
        <FormInput
          v-model="v$.values.name.$model"
          size="large"
          class="update-user-source-form__name-input"
          :placeholder="$t('updateUserSourceForm.nameFieldPlaceholder')"
        />
      </FormGroup>
      <FormGroup
        :label="$t('updateUserSourceForm.integrationFieldLabel')"
        :error-message="getFirstErrorMessage('integration_id')"
        required
        small-label
      >
        <IntegrationDropdown
          v-model="v$.values.integration_id.$model"
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
          class="update-user-source-form__auth-provider"
        >
          <div class="update-user-source-form__auth-provider-header">
            <Checkbox
              :checked="hasAtLeastOneOfThisType(appAuthType)"
              @input="onSelect(appAuthType)"
            >
              {{ appAuthType.name }}
            </Checkbox>

            <ButtonText
              v-if="
                hasAtLeastOneOfThisType(appAuthType) &&
                appAuthType.canCreateNew(appAuthProviderPerTypes)
              "
              icon="iconoir-plus"
              type="secondary"
              @click.prevent="addNew(appAuthType)"
            >
              {{ $t('updateUserSourceForm.addProvider') }}
            </ButtonText>
          </div>

          <div
            v-for="appAuthProvider in appAuthProviderPerTypes[appAuthType.type]"
            :key="appAuthProvider.id"
            class="update-user-source-form__auth-provider-form"
          >
            <component
              :is="appAuthType.formComponent"
              v-if="hasAtLeastOneOfThisType(appAuthType)"
              :ref="`authProviderForm`"
              excluded-form
              :application="builder"
              :integration="integration"
              :user-source="fullValues"
              :auth-providers="appAuthProviderPerTypes"
              :auth-provider="appAuthProvider"
              :default-values="appAuthProvider"
              :auth-provider-type="appAuthType"
              @values-changed="updateAuthProvider(appAuthProvider, $event)"
              @delete="remove(appAuthProvider)"
            />
          </div>
        </div>
      </FormGroup>

      <input type="submit" hidden />
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import AuthProviderWithModal from '@baserow/modules/builder/components/userSource/AuthProviderWithModal'
import { required, maxLength, helpers } from '@vuelidate/validators'

export default {
  components: { IntegrationDropdown, AuthProviderWithModal },
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
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
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
    integrations() {
      return this.$store.getters['integration/getIntegrations'](this.builder)
    },
    integration() {
      if (!this.values.integration_id) {
        return null
      }
      return this.integrations.find(
        ({ id }) => id === this.values.integration_id
      )
    },
    appAuthProviderTypes() {
      return this.$registry
        .getOrderedList('appAuthProvider')
        .filter((type) => !type.isDeactivated(this.builder.workspace.id))
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
    // The problem is that the child provider forms are not handled as a sub array
    // so they override the userSource configuration
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
    /** Return an integer bigger than any of the current auth_provider id to
     * keep the right order when we want to map the error coming back from the server.
     */
    nextID() {
      return (
        Math.max(1, ...this.values.auth_providers.map(({ id }) => id)) + 100
      )
    },
    onSelect(appAuthProviderType) {
      if (this.hasAtLeastOneOfThisType(appAuthProviderType)) {
        this.values.auth_providers = this.values.auth_providers.filter(
          ({ type }) => type !== appAuthProviderType.type
        )
      } else {
        this.values.auth_providers.push({
          type: appAuthProviderType.type,
          id: this.nextID(),
        })
      }
    },
    addNew(appAuthProviderType) {
      this.values.auth_providers.push({
        type: appAuthProviderType.type,
        id: this.nextID(),
      })
    },
    remove(appAuthProvider) {
      this.values.auth_providers = this.values.auth_providers.filter(
        ({ id }) => id !== appAuthProvider.id
      )
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
      this.$emit('values-changed', this.fullValues)
    },
    handleServerError(error) {
      if (
        this.$refs.authProviderForm
          .map((form) => form.handleServerError(error))
          .some((result) => result)
      ) {
        return true
      }
      return false
    },
  },
  validations() {
    return {
      values: {
        integration_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 255 }),
            maxLength(255)
          ),
        },
      },
    }
  },
}
</script>

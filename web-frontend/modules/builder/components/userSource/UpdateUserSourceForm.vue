<template>
  <form @submit.prevent="submit">
    <FormRow>
      <FormGroup
        :label="$t('updateUserSourceForm.nameFieldLabel')"
        :error="v$.name.$error"
        required
        small-label
      >
        <FormInput
          v-model="v$.name.$model"
          size="large"
          class="update-user-source-form__name-input"
          :placeholder="$t('updateUserSourceForm.nameFieldPlaceholder')"
        />

        <template #error>
          <span v-if="v$.name.required.$invalid">
            {{ $t('error.requiredField') }}
          </span>
          <span v-else-if="v$.name.maxLength.$invalid">
            {{ $t('error.maxLength', { max: 255 }) }}
          </span>
        </template>
      </FormGroup>
      <FormGroup
        :label="$t('updateUserSourceForm.integrationFieldLabel')"
        :error="v$.integration_id.$error"
        required
        small-label
      >
        <IntegrationDropdown
          v-model="v$.integration_id.$model"
          :application="builder"
          :integrations="integrations"
          :integration-type="userSourceType.integrationType"
          size="large"
        />

        <template #error>
          <span v-if="v$.integration_id.required.$invalid">
            {{ $t('error.requiredField') }}
          </span>
        </template>
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
              :default-values="appAuthProvider"
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
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import { required, maxLength } from '@vuelidate/validators'
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
      v$: null,
      values: null,
      fullValues: this.getFormValues(),
    }
  },
  computed: {
    integration() {
      if (!this.v$.integration_id.$model) {
        return null
      }
      return this.integrations.find(
        ({ id }) => id === this.v$.integration_id.$model
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
  created() {
    const values = reactive({
      integration_id: null,
      name: null,
    })
    const rules = computed(() => ({
      integration_id: {
        required,
      },
      name: {
        required,
        maxLength: maxLength(255),
      },
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
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
  },
}
</script>

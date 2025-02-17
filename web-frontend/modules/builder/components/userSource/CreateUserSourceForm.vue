<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('createUserSourceForm.userSourceType')"
      :error-message="getFirstErrorMessage('type')"
      required
      small-label
      class="margin-bottom-2"
      size="large"
    >
      <Dropdown
        v-model="v$.values.type.$model"
        :error="v$.values.type.$error"
        :show-search="false"
        class="user-source-settings__user-source-type"
        size="large"
      >
        <DropdownItem
          v-for="userSourceType in userSourceTypes"
          :key="userSourceType.type"
          :name="userSourceType.name"
          :value="userSourceType.type"
          :image="userSourceType.integrationType.image"
        />
      </Dropdown>
    </FormGroup>
    <FormGroup
      :label="$t('createUserSourceForm.userSourceIntegration')"
      :error-message="getFirstErrorMessage('integration_id')"
      required
      small-label
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="v$.values.integration_id.$model"
        :error="v$.values.integration_id.$error"
        :application="builder"
        :integrations="integrations"
        :integration-type="currentUserSourceType?.integrationType"
        size="large"
      />
    </FormGroup>

    <FormGroup
      :label="$t('createUserSourceForm.userSourceName')"
      required
      small-label
      :error-message="getFirstErrorMessage('name')"
    >
      <FormInput
        v-model="v$.values.name.$model"
        :error="v$.values.name.$error"
        size="large"
      />
    </FormGroup>

    <input type="submit" hidden />
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import { required, maxLength, helpers } from '@vuelidate/validators'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'

export default {
  name: 'CreateUserSourceForm',
  components: { IntegrationDropdown },
  mixins: [form],
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: { type: null, name: '', integration_id: null },
    }
  },
  computed: {
    integrations() {
      return this.$store.getters['integration/getIntegrations'](this.builder)
    },
    userSources() {
      return this.$store.getters['userSource/getUserSources'](this.builder)
    },
    userSourceTypes() {
      return Object.values(this.$registry.getOrderedList('userSource'))
    },
    currentUserSourceType() {
      if (this.values.type)
        return this.$registry.get('userSource', this.values.type)

      return null
    },
    userSourceNames() {
      return this.userSources.map(({ name }) => name)
    },
  },
  watch: {
    currentUserSourceType(newValue) {
      this.v$.values.name.$model = getNextAvailableNameInSequence(
        newValue.name,
        this.userSourceNames
      )
    },
  },
  methods: {
    handleServerError() {
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
        type: {
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

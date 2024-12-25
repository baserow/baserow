<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('createUserSourceForm.userSourceType')"
      :error-message="getError('type')"
      required
      small-label
      class="margin-bottom-2"
      size="large"
    >
      <Dropdown
        v-model="$v.values.type.$model"
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
      :error-message="getError('integration_id')"
      required
      small-label
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="$v.values.integration_id.$model"
        :application="builder"
        :integrations="integrations"
        :integration-type="currentUserSourceType?.integrationType"
        size="large"
      />
    </FormGroup>

    <FormGroup
      :error-message="getError('name')"
      :label="$t('createUserSourceForm.userSourceName')"
      required
      small-label
    >
      <FormInput v-model="$v.values.name.$model" size="large" />
    </FormGroup>

    <input type="submit" hidden />
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import { required, maxLength } from 'vuelidate/lib/validators'
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
      if (!this.values.type) {
        return null
      } else {
        return this.$registry.get('userSource', this.values.type)
      }
    },
    userSourceNames() {
      return this.userSources.map(({ name }) => name)
    },
  },
  watch: {
    currentUserSourceType(newValue) {
      this.values.name = getNextAvailableNameInSequence(
        newValue.name,
        this.userSourceNames
      )
    },
  },
  methods: {
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

    handleServerError() {
      return false
    },
  },
  validations: {
    values: {
      type: {
        required,
      },
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

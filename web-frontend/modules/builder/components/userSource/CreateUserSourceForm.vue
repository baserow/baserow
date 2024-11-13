<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('createUserSourceForm.userSourceType')"
      :error="v$.type.$error"
      required
      small-label
      class="margin-bottom-2"
      size="large"
    >
      <Dropdown
        v-model="v$.type.$model"
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

      <template #error>
        <span v-if="v$.type.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>
    <FormGroup
      :label="$t('createUserSourceForm.userSourceIntegration')"
      :error="v$.integration_id.$error"
      required
      small-label
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="v$.integration_id.$model"
        :application="builder"
        :integrations="integrations"
        :integration-type="currentUserSourceType?.integrationType"
        size="large"
      />

      <template #error>
        <span v-if="v$.integration_id.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      :error="v$.name.$error"
      :label="$t('createUserSourceForm.userSourceName')"
      required
      small-label
    >
      <FormInput v-model="v$.name.$model" size="large" />

      <template #error>
        <span v-if="v$.name.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.name.maxLength.$invalid">
          {{ $t('error.maxLength', { max: 255 }) }}
        </span>
      </template>
    </FormGroup>

    <input type="submit" hidden />
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import { required, maxLength } from '@vuelidate/validators'
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
    integrations: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      values: null,
      v$: null,
    }
  },
  computed: {
    userSources() {
      return this.$store.getters['userSource/getUserSources'](this.builder)
    },
    userSourceTypes() {
      return Object.values(this.$registry.getOrderedList('userSource'))
    },
    currentUserSourceType() {
      if (this.v$?.type.$model)
        return this.$registry.get('userSource', this.v$.type.$model)

      return null
    },
    userSourceNames() {
      return this.userSources.map(({ name }) => name)
    },
  },
  watch: {
    currentUserSourceType(newValue) {
      this.v$.name.$model = getNextAvailableNameInSequence(
        newValue.name,
        this.userSourceNames
      )
    },
  },
  created() {
    const values = reactive({
      integration_id: null,
      name: null,
      type: null,
    })

    const rules = computed(() => ({
      integration_id: {
        required,
      },
      name: {
        required,
        maxLength: maxLength(255),
      },
      type: {
        required,
      },
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>

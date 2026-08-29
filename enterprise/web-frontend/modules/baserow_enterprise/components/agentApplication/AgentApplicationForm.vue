<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="v$.values.name.$error"
      small-label
      :label="$t('applicationForm.nameLabel')"
      required
    >
      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        size="large"
        :error="v$.values.name.$error"
        @focus.once="$event.target.select()"
        @blur="v$.values.name.$touch"
      >
      </FormInput>

      <template #error>
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('agentApplicationForm.descriptionLabel')"
      :helper-text="$t('agentApplicationForm.descriptionHelper')"
      class="margin-top-2"
    >
      <FormTextarea
        v-model="values.description"
        :rows="4"
        :placeholder="$t('agentApplicationForm.descriptionPlaceholder')"
      ></FormTextarea>
    </FormGroup>

    <div class="actions actions--right">
      <Button
        type="primary"
        size="large"
        :loading="loading"
        :disabled="loading"
      >
        {{ $t('action.add') }}
        {{ $filters.lowercase(agentApplicationType.getName()) }}
      </Button>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'AgentApplicationForm',
  mixins: [form],
  props: {
    defaultName: {
      type: String,
      required: false,
      default: '',
    },
    loading: {
      type: Boolean,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['submitted'],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        name: this.defaultName,
        description: '',
      },
    }
  },
  computed: {
    agentApplicationType() {
      return this.$registry.get('application', 'agent')
    },
  },
  mounted() {
    this.$refs.name?.focus()
  },
  validations() {
    return {
      values: {
        name: { required },
      },
    }
  },
}
</script>

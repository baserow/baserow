<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="v$.values.prompt.$error"
      :label="$t('aiDatabaseOnboardingForm.label')"
      small-label
      required
    >
      <FormTextarea
        v-model="values.prompt"
        ref="promptInput"
        :placeholder="$t('aiDatabaseOnboardingForm.placeholder')"
        size="large"
        rows="4"
        :error="v$.values.prompt.$error"
        @blur="v$.values.prompt.$touch"
        @input=";[v$.values.prompt.$touch(), updateValue()]"
      />
      <template #error>{{ v$.values.prompt.$errors[0].$message }}</template>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'

export default {
  name: 'AIDatabaseOnboardingForm',
  mixins: [form],
  emits: ['input'],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  mounted() {
    this.$nextTick(() => {
      this.$refs.promptInput.focus()
    })
  },
  data() {
    return {
      values: {
        prompt: '',
      },
    }
  },
  methods: {
    updateValue() {
      this.$nextTick(() => {
        this.$emit('input', this.values)
      })
    }
  },
  validations() {
    return {
      values: {
        prompt: { required },
      },
    }
  },
}
</script>

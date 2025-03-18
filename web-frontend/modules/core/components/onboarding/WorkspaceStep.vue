<template>
  <div>
    <h1>{{ $t('workspaceStep.title') }}</h1>

    <FormGroup :error="v$.name.$error">
      <FormInput
        v-model="v$.name.$model"
        :placeholder="$t('workspaceStep.workspaceLabel') + '...'"
        :label="$t('workspaceStep.workspaceLabel')"
        size="large"
        :error="v$.name.$error"
        @input="updateValue"
        @blur="v$.name.$touch"
      />
      <template #error> {{ v$.name.$errors[0]?.$message }} </template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'

export default {
  name: 'WorkspaceStep',
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      name: this.$store.getters['auth/getName'] + "'s workspace",
    }
  },

  mounted() {
    this.updateValue()
  },
  methods: {
    isValid() {
      return !this.v$.$invalid && this.v$.$dirty
    },
    updateValue() {
      this.v$.name.$touch()
      this.$emit('update-data', { name: this.name })
    },
  },
  validations() {
    return {
      name: {
        required: helpers.withMessage(this.$t('error.requiredField'), required),
      },
    }
  },
}
</script>

<template>
  <div>
    <h1>{{ $t('workspaceStep.title') }}</h1>

    <FormGroup :error="v$.name.$dirty && !v$.name.required">
      <FormInput
        v-model="name"
        :placeholder="$t('workspaceStep.workspaceLabel') + '...'"
        :label="$t('workspaceStep.workspaceLabel')"
        size="large"
        :error="v$.name.$dirty && !v$.name.required"
        @input="updateValue"
        @blur="v$.name.$touch()"
      />
      <template #error>{{ $t('error.requiredField') }}</template>
    </FormGroup>
  </div>
</template>

<script>
import { required } from '@vuelidate/validators'

export default {
  name: 'WorkspaceStep',
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
      return !this.v$.$invalid
    },
    updateValue() {
      this.v$.name.$touch()
      this.$emit('update-data', { name: this.name })
    },
  },
  validations() {
    return {
      name: { required },
    }
  },
}
</script>

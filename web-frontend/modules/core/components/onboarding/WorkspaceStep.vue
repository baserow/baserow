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
      <template #error>{{ $t('error.requiredField') }}</template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required } from '@vuelidate/validators'

export default {
  name: 'WorkspaceStep',
  data() {
    return {
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      name: this.$store.getters['auth/getName'] + "'s workspace",
    })

    const rules = computed(() => ({
      name: {
        required,
      },
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
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
}
</script>

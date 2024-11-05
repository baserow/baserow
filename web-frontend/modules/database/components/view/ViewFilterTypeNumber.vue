<template>
  <FormInput
    ref="input"
    v-model="copy"
    :error="v$.copy.$error"
    :disabled="disabled"
    @input="delayedUpdate($event)"
    @keydown.enter="delayedUpdate($event.target.value, true)"
  >
  </FormInput>
</template>

<script>
import { decimal } from '@vuelidate/validators'

import filterTypeInput from '@baserow/modules/database/mixins/filterTypeInput'

export default {
  name: 'ViewFilterTypeNumber',
  mixins: [filterTypeInput],
  methods: {
    focus() {
      this.$refs.input.focus()
    },
  },
  validations: {
    copy: { decimal },
  },
}
</script>

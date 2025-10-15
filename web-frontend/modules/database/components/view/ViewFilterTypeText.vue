<template>
  <FormInput
    ref="input"
    v-model="copy"
    :error="v$.copy.$error"
    :disabled="disabled"
    :placeholder="placeholder"
    @input="delayedUpdate($event)"
    @keydown.enter="delayedUpdate($event.target.value, true)"
  >
  </FormInput>
</template>

<script>
import filterTypeInput from '@baserow/modules/database/mixins/filterTypeInput'

export default {
  name: 'ViewFilterTypeText',
  mixins: [filterTypeInput],
  methods: {
    focus() {
      this.$refs.input.focus()
    },
  },
}
</script>

<template>
  <FormInput
    ref="input"
    v-model="v$.copy.$model"
    :error="v$.copy.$error"
    :disabled="disabled"
    @input="delayedUpdate($event)"
    @keydown.enter="delayedUpdate($event.target.value, true)"
  >
  </FormInput>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { computed } from 'vue'
import { decimal } from '@vuelidate/validators'

import filterTypeInput from '@baserow/modules/database/mixins/filterTypeInput'

export default {
  name: 'ViewFilterTypeNumber',
  mixins: [filterTypeInput],
  data() {
    return {
      values: null,
      v$: null,
    }
  },
  created() {
    const rules = computed(() => ({
      copy: { decimal },
    }))
    this.v$ = useVuelidate(rules, this.values, { $lazy: true })
  },
  methods: {
    focus() {
      this.$refs.input.focus()
    },
  },
}
</script>

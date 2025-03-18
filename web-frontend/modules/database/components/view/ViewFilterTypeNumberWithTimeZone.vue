<template>
  <div class="filters__multi-value">
    <FormInput
      ref="input"
      v-model="v$.xAgo.$model"
      type="text"
      :error="v$.xAgo.$error"
      :disabled="disabled"
      @input=";[setCopy($event), delayedUpdate($event, true)]"
      @keydown.enter=";[setCopy($event), delayedUpdate($event, true)]"
    ></FormInput>

    <span class="filters__value-timezone">{{ getTimezoneAbbr() }}</span>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { integer, required } from '@vuelidate/validators'
import filterTypeDateInput from '@baserow/modules/database/mixins/filterTypeDateInput'

export default {
  name: 'ViewFilterTypeNumberWithTimeZone',
  mixins: [filterTypeDateInput],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      xAgo: '',
    }
  },
  methods: {
    isInputValid() {
      return !this.v$.xAgo.$error
    },
    setCopy(value, sender) {
      const [, xAgo] = this.splitCombinedValue(value)
      this.xAgo = xAgo
    },
  },
  validations() {
    return {
      copy: { required },
      xAgo: { integer },
    }
  },
}
</script>

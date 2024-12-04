<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('registerLicenseForm.licenseKey')"
      :error="v$.license.$error"
    >
      <FormTextarea
        ref="license"
        v-model="v$.license.$model"
        :error="v$.license.$error"
        :rows="6"
        @blur="v$.license.$touch"
      />

      <template #error>
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'RegisterLicenseForm',
  mixins: [form],
  data() {
    return {
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      license: '',
    })

    const rules = computed(() => ({
      license: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  mounted() {
    this.$refs.license.focus()
  },
}
</script>

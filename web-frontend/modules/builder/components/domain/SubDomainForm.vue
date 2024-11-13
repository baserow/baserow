<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('subDomainForm.domainNameLabel')"
      small-label
      required
      :error="v$.domain_name.$error || Boolean(serverErrors.domain_name)"
    >
      <FormInput
        v-model="v$.domain_name.$model"
        @input="serverErrors.domain_name = null"
      >
        <template #suffix> .{{ domain }} </template>
      </FormInput>

      <template #error>
        <span v-if="v$.domain_name.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.domain_name.maxLength.$invalid">
          {{ $t('error.maxLength', { max: 255 }) }}
        </span>
        <span
          v-else-if="
            serverErrors.domain_name &&
            serverErrors.domain_name.code === 'invalid'
          "
        >
          {{ $t('domainForm.invalidDomain') }}
        </span>
        <span
          v-else-if="
            serverErrors.domain_name &&
            serverErrors.domain_name.code === 'unique'
          "
        >
          {{ $t('domainForm.notUniqueDomain') }}
        </span>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { maxLength, required } from '@vuelidate/validators'
import domainForm from '@baserow/modules/builder/mixins/domainForm'

export default {
  name: 'SubDomainForm',
  mixins: [domainForm],
  data() {
    return {
      domainPrefix: '',
      values: null,
      v$: null,
    }
  },

  watch: {
    domainPrefix(value) {
      this.values.domain_name = `${value}.${this.domain}`
    },
  },
  created() {
    const values = reactive({
      domain_name: '',
    })

    const rules = computed(() => ({
      domain_name: {
        required,
        maxLength: maxLength(255),
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>

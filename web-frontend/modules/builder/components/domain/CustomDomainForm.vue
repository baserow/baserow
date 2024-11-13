<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      required
      :label="$t('customDomainForm.domainNameLabel')"
      :error="v$.domain_name.$error || Boolean(serverErrors.domain_name)"
    >
      <FormInput
        v-model="v$.domain_name.$model"
        size="large"
        @input="serverErrors.domain_name = null"
        @blur="v$.domain_name.$touch"
      />

      <template #error>
        <span v-if="v$.domain_name.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.domain_name.maxLength.$invalid">
          {{ $t('error.maxLength', { max: 255 }) }}
        </span>

        <div v-if="serverErrors.domain_name">
          <span v-if="serverErrors.domain_name.code === 'invalid'">
            {{ $t('domainForm.invalidDomain') }}
          </span>
          <span v-if="serverErrors.domain_name.code === 'unique'">
            {{ $t('domainForm.notUniqueDomain') }}
          </span>
        </div>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required, maxLength } from '@vuelidate/validators'
import domainForm from '@baserow/modules/builder/mixins/domainForm'

export default {
  name: 'CustomDomainForm',
  mixins: [domainForm],
  data() {
    return {
      values: null,
      v$: null,
    }
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

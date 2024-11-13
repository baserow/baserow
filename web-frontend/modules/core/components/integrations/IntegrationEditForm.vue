<template>
  <form ref="form" @submit.prevent="submit">
    <FormGroup required class="margin-bottom-2" :error="v$.name.$error">
      <FormInput
        v-model="v$.name.$model"
        required
        :label="$t('integrationEditForm.name')"
        :placeholder="$t('integrationEditForm.namePlaceholder')"
        @blur="v$.name.$touch"
      />

      <template #error>
        <span v-if="v$.name.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-if="v$.name.maxLength.$invalid">
          {{ $t('error.maxLength', { max: 255 }) }}
        </span>
      </template>
    </FormGroup>

    <component
      :is="integrationType.formComponent"
      :application="application"
      :default-values="defaultValues"
    />
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import { required, maxLength } from '@vuelidate/validators'

export default {
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
    integrationType: {
      type: Object,
      required: true,
    },
  },
  data() {
    return { v$: null, values: null, allowedValues: ['name'] }
  },
  created() {
    const values = reactive({
      name: '',
    })

    const rules = computed(() => ({
      name: {
        required,
        maxLength: maxLength(255),
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>

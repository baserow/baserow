<template>
  <form @submit.prevent="submit">
    <SelectAIModelForm
      :database="database"
      :default-values="defaultValues"
    ></SelectAIModelForm>

    <FormGroup
      class="margin-bottom-2 margin-top-2"
      small-label
      required
      :label="$t('aiFormulaModal.label')"
      :help-text="$t('aiFormulaModal.labelDescription')"
      :error="v$.ai_prompt.$error"
    >
      <FormTextarea
        v-model="v$.ai_prompt.$model"
        :error="v$.ai_prompt.$error"
        auto-expandable
        :min-rows="5"
        @input="v$.ai_prompt.$touch"
      >
      </FormTextarea>
      <template #error>
        <div v-if="v$.ai_prompt.required.$invalid">
          {{ $t('error.requiredField') }}
        </div>
        <span v-else-if="v$.ai_prompt.maxLength.$invalid">
          {{
            $t('error.maxLength', {
              max: v$.ai_prompt.$params.maxLength.max,
            })
          }}</span
        >
      </template>
    </FormGroup>
    <div class="align-right">
      <slot></slot>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import SelectAIModelForm from '@baserow/modules/core/components/ai/SelectAIModelForm'
import { required, maxLength } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'AIFormulaForm',
  components: { SelectAIModelForm },
  mixins: [form],
  props: {
    database: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      allowedValues: ['ai_prompt'],
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      ai_prompt: '',
    })

    const rules = computed(() => ({
      ai_prompt: {
        required,
        maxLength: maxLength(1000),
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>

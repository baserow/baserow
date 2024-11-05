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
      :error="fieldHasErrors('ai_prompt')"
    >
      <FormTextarea
        v-model="v$.values.ai_prompt.$model"
        :error="fieldHasErrors('ai_prompt')"
        auto-expandable
        :min-rows="5"
        @input="v$.values.ai_prompt.$touch"
      >
      </FormTextarea>
      <template #error>
        {{ v$.values.ai_prompt.$errors[0]?.$message }}
      </template>
    </FormGroup>
    <div class="align-right">
      <slot></slot>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import SelectAIModelForm from '@baserow/modules/core/components/ai/SelectAIModelForm'
import { required, maxLength, helpers } from '@vuelidate/validators'

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
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['ai_prompt'],
      values: {
        ai_prompt: '',
      },
    }
  },
  validations() {
    return {
      values: {
        ai_prompt: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', {
              max: 1000,
            }),
            maxLength(1000)
          ),
        },
      },
    }
  },
}
</script>

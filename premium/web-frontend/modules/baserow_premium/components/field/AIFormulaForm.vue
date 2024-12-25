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
      :error="$v.values.ai_prompt.$dirty && $v.values.ai_prompt.$error"
    >
      <FormTextarea
        v-model="values.ai_prompt"
        :error="$v.values.ai_prompt.$dirty && $v.values.ai_prompt.$error"
        auto-expandable
        :min-rows="5"
        @input="$v.values.ai_prompt.$touch()"
      >
      </FormTextarea>
      <template #error>
        <div v-if="$v.values.ai_prompt.$dirty && !$v.values.ai_prompt.required">
          {{ $t('error.requiredField') }}
        </div>
        <span
          v-else-if="
            $v.values.ai_prompt.$dirty && !$v.values.ai_prompt.maxLength
          "
        >
          {{
            $t('error.maxLength', {
              max: $v.values.ai_prompt.$params.maxLength.max,
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
import SelectAIModelForm from '@baserow/modules/core/components/ai/SelectAIModelForm'
import { required, maxLength } from 'vuelidate/lib/validators'

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
      values: {
        ai_prompt: '',
      },
    }
  },
  validations: {
    values: {
      ai_prompt: {
        required,
        maxLength: maxLength(1000),
      },
    },
  },
}
</script>

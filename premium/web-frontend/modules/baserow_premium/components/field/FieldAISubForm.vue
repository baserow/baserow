<template>
  <div v-if="!isDeactivated" class="context__form-container">
    <SelectAIModelForm
      :default-values="defaultValues"
      :database="database"
      @ai-type-changed="setFileFieldSupported"
    ></SelectAIModelForm>

    <FormGroup v-if="fileFieldSupported" required small-label>
      <template #label>
        {{ $t('selectAIModelForm.fileField') }}
        <HelpIcon
          :tooltip="$t('fieldAISubForm.fileFieldHelp')"
          :tooltip-content-classes="['tooltip__content--expandable']"
        />
      </template>

      <Dropdown
        v-model="values.ai_file_field_id"
        class="dropdown--floating"
        :error="v$.values.ai_file_field_id.$error"
        :fixed-items="true"
        :show-search="false"
        @hide="v$.values.ai_file_field_id.$touch()"
      >
        <DropdownItem
          :name="$t('fieldAISubForm.emptyFileField')"
          :value="null"
        />
        <DropdownItem
          v-for="field in fileFields"
          :key="field.id"
          :name="field.name"
          :value="field.id"
        />
      </Dropdown>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('fieldAISubForm.prompt')"
      :error="v$.values.ai_prompt.$dirty && v$.values.ai_prompt.$error"
      required
    >
      <div style="max-width: 366px">
        <FormulaInputField
          v-model="values.ai_prompt"
          :data-providers="dataProviders"
          :application-context="applicationContext"
          :placeholder="$t('fieldAISubForm.promptPlaceholder')"
          @input="v$.values.ai_prompt.$touch()"
        ></FormulaInputField>
      </div>
      <template #error> {{ $t('error.requiredField') }}</template>
    </FormGroup>
  </div>
  <div v-else>
    <p>
      {{ $t('fieldAISubForm.premiumFeature') }} <i class="iconoir-lock"></i>
    </p>
  </div>
</template>

<script>
import { required } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import SelectAIModelForm from '@baserow/modules/core/components/ai/SelectAIModelForm'

export default {
  name: 'FieldAISubForm',
  components: { SelectAIModelForm, FormulaInputField },
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: ['ai_prompt', 'ai_file_field_id'],
      values: {
        ai_prompt: '',
        ai_file_field_id: null,
      },
      fileFieldSupported: false,
    }
  },
  computed: {
    // Return the reactive object that can be updated in runtime.
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    applicationContext() {
      const context = {}
      Object.defineProperty(context, 'fields', {
        enumerable: true,
        get: () =>
          this.allFieldsInTable.filter((f) => {
            const isNotThisField = f.id !== this.defaultValues.id
            return isNotThisField
          }),
      })
      return context
    },
    dataProviders() {
      return [this.$registry.get('databaseDataProvider', 'fields')]
    },
    isDeactivated() {
      return this.$registry
        .get('field', this.fieldType)
        .isDeactivated(this.workspace.id)
    },
    fileFields() {
      return this.allFieldsInTable.filter((field) => {
        const t = this.$registry.get('field', field.type)
        return t.canRepresentFiles(field)
      })
    },
  },
  methods: {
    setFileFieldSupported(generativeAIType) {
      if (generativeAIType) {
        const modelType = this.$registry.get(
          'generativeAIModel',
          generativeAIType
        )
        this.fileFieldSupported = modelType.canPromptWithFiles()
      } else {
        this.fileFieldSupported = false
      }

      if (!this.fileFieldSupported) {
        this.values.ai_file_field_id = null
      }
    },
  },
  validations: {
    values: {
      ai_prompt: { required },
      ai_file_field_id: {},
    },
  },
}
</script>

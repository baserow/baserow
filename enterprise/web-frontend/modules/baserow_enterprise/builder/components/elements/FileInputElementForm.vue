<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="v$.values.styles.$model"
      style-key="input"
      :config-block-types="['input', 'typography']"
      :extra-args="{ onlyBody: true, noAlignment: true }"
      :theme="builder.theme"
    />
    <FormGroup
      :label="$t('generalForm.labelTitle')"
      class="margin-bottom-2"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="v$.values.label.$model"
        :placeholder="$t('generalForm.labelPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('fileInputElementForm.helpTextTitle')"
      class="margin-bottom-2"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="v$.values.help_text.$model"
        :placeholder="$t('fileInputElementForm.helpTextPlaceholder')"
      />
    </FormGroup>
    <hr />
    <FormGroup
      :label="
        $tc('fileInputElementForm.defaultUrlTitle', values.multiple ? 2 : 1)
      "
      class="margin-bottom-2"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="v$.values.default_url.$model"
        :placeholder="
          $tc(
            'fileInputElementForm.defaultUrlPlaceholder',
            values.multiple ? 2 : 1
          )
        "
      />
    </FormGroup>
    <FormGroup
      :label="
        $tc('fileInputElementForm.defaultNameTitle', values.multiple ? 2 : 1)
      "
      class="margin-bottom-2"
      :helper-text="
        values.multiple ? $t('fileInputElementForm.defaultNameHelp') : ''
      "
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="v$.values.default_name.$model"
        :placeholder="
          $tc(
            'fileInputElementForm.defaultNamePlaceholder',
            values.multiple ? 2 : 1
          )
        "
      />
    </FormGroup>
    <hr />
    <FormGroup
      :label="$t('fileInputElementForm.required')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="v$.values.required.$model"></Checkbox>
    </FormGroup>
    <hr />
    <FormGroup
      :label="$t('fileInputElementForm.multiple')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="v$.values.multiple.$model"></Checkbox>
    </FormGroup>
    <hr />
    <FormGroup
      required
      small-label
      :label="$t('fileInputElementForm.preview')"
      class="margin-bottom-2"
    >
      <Checkbox v-model="v$.values.preview.$model"></Checkbox>
    </FormGroup>
    <hr />
    <FormGroup
      required
      small-label
      :label="$t('fileInputElementForm.fileTypes')"
      class="margin-bottom-2"
      :helper-text="$t('fileInputElementForm.fileTypesHelper')"
    >
      <template #after-label>
        <ButtonText
          type="primary"
          icon="iconoir-plus"
          size="small"
          @click="addFileType"
        >
          {{ $t('fileInputElementForm.addFileType') }}
        </ButtonText></template
      >
      <div
        v-for="(fileType, index) in v$.values.allowed_filetypes.$model"
        :key="index"
        class="margin-bottom-1 file-input-element-form__file-type"
      >
        <FormInput
          :value="fileType"
          class="file-input-element-form__file-type-input"
          @input="updateFileType(index, $event)"
        />
        <ButtonIcon icon="iconoir-bin" @click="deleteFileType(index)" />
      </div>
    </FormGroup>
    <FormGroup
      class="margin-bottom-2"
      small-label
      :label="$t('fileInputElementForm.maxFileSize')"
      required
      :error-message="getFirstErrorMessage('max_filesize')"
    >
      <FormInput
        v-model="v$.values.max_filesize.$model"
        :placeholder="$t('fileInputElementForm.maxFileSizePlaceholder')"
        :to-value="(value) => parseInt(value)"
        type="number"
        remove-number-input-controls
        @blur="v$.values.max_filesize.$touch"
      >
        <template #suffix>MB</template>
      </FormInput>
    </FormGroup>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import formElementForm from '@baserow/modules/builder/mixins/formElementForm'
import { useVuelidate } from '@vuelidate/core'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'

export default {
  name: 'FileInputElementForm',
  components: { InjectedFormulaInput, CustomStyleButton },
  mixins: [formElementForm],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        label: {},
        default_name: {},
        default_url: {},
        help_text: {},
        required: false,
        multiple: false,
        max_filesize: 5,
        allowed_filetypes: [],
        styles: {},
        preview: false,
      },
      allowedValues: [
        'styles',
        'label',
        'required',
        'multiple',
        'default_name',
        'default_url',
        'help_text',
        'max_filesize',
        'allowed_filetypes',
        'preview',
      ],
    }
  },
  methods: {
    addFileType() {
      this.v$.values.allowed_filetypes.$model.push('')
    },
    updateFileType(index, newValue) {
      this.v$.values.allowed_filetypes.$model =
        this.v$.values.allowed_filetypes.$model.map((value, i) =>
          index === i ? newValue : value
        )
    },
    deleteFileType(index) {
      this.v$.values.allowed_filetypes.$model.splice(index, 1)
    },
  },
  validations() {
    return {
      values: {
        label: {},
        required: {},
        multiple: {},
        styles: {},
        default_name: {},
        default_url: {},
        help_text: {},
        max_filesize: {
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 1 }),
            minValue(1)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 100 }),
            maxValue(100)
          ),
        },
        allowed_filetypes: {},
        preview: {},
      },
    }
  },
}
</script>

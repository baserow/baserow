<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="input"
      :config-block-types="['input']"
      :theme="builder.theme"
    />
    <FormGroup
      small-label
      :label="$t('generalForm.labelTitle')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.label"
        :placeholder="$t('generalForm.labelPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('generalForm.valueTitle')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.default_value"
        :placeholder="$t('generalForm.valuePlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('generalForm.placeholderTitle')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.placeholder"
        :placeholder="$t('generalForm.placeholderPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('generalForm.requiredTitle')"
      class="margin-bottom-2"
      small-label
      required
    >
      <Checkbox v-model="values.required"></Checkbox>
    </FormGroup>

    <FormGroup
      :label="$t('choiceElementForm.multiple')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="values.multiple"></Checkbox>
    </FormGroup>

    <FormGroup
      :label="$t('choiceElementForm.display')"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="values.show_as_dropdown"
        :options="displayOptions"
        type="button"
      />
    </FormGroup>

    <FormGroup
      :label="$t('choiceOptionSelector.optionType')"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioButton
        v-model="values.option_type"
        type="chips"
        :value="CHOICE_OPTION_TYPES.MANUAL"
        icon="iconoir-open-select-hand-gesture"
      >
        {{ $t('choiceOptionSelector.manual') }}
      </RadioButton>
      <RadioButton
        v-model="values.option_type"
        type="chips"
        :value="CHOICE_OPTION_TYPES.FORMULAS"
        icon="iconoir-sigma-function"
      >
        {{ $t('choiceOptionSelector.formulas') }}
      </RadioButton>
    </FormGroup>
    <template v-if="values.option_type === CHOICE_OPTION_TYPES.MANUAL">
      <template v-if="values.options.length">
        <div class="row" style="--gap: 6px">
          <label class="col col-5 control__label control__label--small">
            {{ $t('choiceOptionSelector.name') }}
          </label>
          <label class="col col-7 control__label control__label--small">
            {{ $t('choiceOptionSelector.value') }}
          </label>
        </div>
        <div
          v-for="option in values.options"
          :key="option.id"
          style="--gap: 6px"
          class="row margin-bottom-1"
        >
          <div class="col col-5">
            <FormInput
              v-model="option.name"
              :placeholder="$t('choiceOptionSelector.namePlaceholder')"
            />
          </div>
          <div class="col col-5">
            <FormInput
              :value="option.value === null ? option.name : option.value"
              :placeholder="$t('choiceOptionSelector.valuePlaceholder')"
              :class="{
                'choice-element__option-value--fake': option.value === null,
              }"
              @input="option.value = $event"
            />
          </div>
          <div class="col col-2">
            <ButtonIcon icon="iconoir-bin" @click="deleteOption(option)" />
          </div>
        </div>
      </template>
      <template v-else>
        <div class="row" style="--gap: 6px">
          <label class="col control__label control__label--small">
            {{ $t('choiceOptionSelector.addOptionDescription') }}
          </label>
        </div>
      </template>
      <ButtonText
        type="secondary"
        size="small"
        icon="iconoir-plus"
        :loading="loading"
        @click="createOption"
      >
        {{ $t('choiceOptionSelector.addOption') }}
      </ButtonText>
    </template>
    <template v-else-if="values.option_type === CHOICE_OPTION_TYPES.FORMULAS">
      <FormGroup
        small-label
        :label="$t('choiceOptionSelector.name')"
        class="margin-bottom-2"
      >
        <InjectedFormulaInput
          v-model="values.formula_name"
          :placeholder="$t('choiceOptionSelector.namePlaceholder')"
        />
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('choiceOptionSelector.value')"
        class="margin-bottom-2"
        required
      >
        <InjectedFormulaInput
          v-model="values.formula_value"
          :placeholder="$t('choiceOptionSelector.valuePlaceholder')"
        />
      </FormGroup>
    </template>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import { CHOICE_OPTION_TYPES } from '@baserow/modules/builder/enums'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import formElementForm from '@baserow/modules/builder/mixins/formElementForm'
import { uuid } from '@baserow/modules/core/utils/string'

export default {
  name: 'ChoiceElementForm',
  components: {
    InjectedFormulaInput,
    CustomStyleButton,
  },
  mixins: [formElementForm],
  props: {
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      allowedValues: [
        'label',
        'default_value',
        'required',
        'placeholder',
        'options',
        'multiple',
        'show_as_dropdown',
        'option_type',
        'formula_name',
        'formula_value',
        'styles',
      ],
      values: {
        label: {},
        default_value: {},
        required: false,
        placeholder: {},
        options: [],
        multiple: false,
        show_as_dropdown: true,
        option_type: CHOICE_OPTION_TYPES.MANUAL,
        formula_name: {},
        formula_value: {},
        styles: {},
      },
    }
  },
  computed: {
    CHOICE_OPTION_TYPES: () => CHOICE_OPTION_TYPES,
    element() {
      return this.$store.getters['element/getElementById'](
        this.elementPage,
        this.values.id
      )
    },
    displayOptions() {
      return [
        {
          title: this.$t('choiceElementForm.dropdown'),
          label: this.$t('choiceElementForm.dropdown'),
          value: true,
          icon: 'iconoir-list',
        },
        {
          title: this.values.multiple
            ? this.$t('choiceElementForm.checkbox')
            : this.$t('choiceElementForm.radio'),
          label: this.values.multiple
            ? this.$t('choiceElementForm.checkbox')
            : this.$t('choiceElementForm.radio'),
          value: false,
          icon: this.values.multiple
            ? 'baserow-icon-check-square'
            : 'iconoir-check-circle',
        },
      ]
    },
  },
  watch: {
    'element.options'(options) {
      this.values.options = { ...options }
    },
  },
  methods: {
    createOption() {
      this.values.options.push({ name: '', value: null, id: uuid() })
    },
    deleteOption({ id }) {
      this.values.options = this.values.options.filter(
        (option) => option.id !== id
      )
    },
  },
}
</script>

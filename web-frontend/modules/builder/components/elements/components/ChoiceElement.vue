<template>
  <ABFormGroup
    :label="labelResolved"
    :required="element.required"
    :error-message="displayFormDataError ? $t('error.requiredField') : ''"
    :style="getStyleOverride('input')"
  >
    <template #label>
      <FormattedText
        :content="labelResolved"
        :format="element.label_format"
        preset="inlineLinks"
      />
    </template>
    <ABDropdown
      v-if="element.show_as_dropdown"
      v-model="inputValue"
      class="choice-element"
      :placeholder="
        canHaveOptions ? placeholderResolved : $t('choiceElement.addOptions')
      "
      :show-search="false"
      :multiple="element.multiple"
      :clearable="!element.multiple && !element.required"
      @hide="onFormElementTouch"
    >
      <template v-if="hasMarkdownOptions" #value>
        <span class="ab-dropdown__selected-text">
          <template v-for="(name, index) in selectedOptionNames" :key="index">
            <template v-if="index > 0">, </template>
            <FormattedText
              :content="name"
              :format="element.option_format"
              preset="inline"
            />
          </template>
        </span>
      </template>
      <ABDropdownItem
        v-for="option in optionsResolved"
        :key="option.id"
        :name="dropdownOptionName(option)"
        :value="option.value"
      >
        <!--
        The search and the tooltip keep using the raw option name; only the
        visible text is rendered.
        -->
        <span
          class="ab-dropdownitem__item-name-text"
          :title="dropdownOptionName(option)"
        >
          <FormattedText
            :content="dropdownOptionName(option)"
            :format="element.option_format"
            preset="inline"
          />
        </span>
      </ABDropdownItem>
    </ABDropdown>
    <template v-else>
      <template v-if="canHaveOptions">
        <template v-if="element.multiple">
          <ABCheckbox
            v-for="option in optionsResolved"
            :key="option.id"
            :read-only="isEditMode"
            :error="displayFormDataError"
            :model-value="inputValue.includes(option.value)"
            @update:model-value="onOptionChange(option, $event)"
          >
            <FormattedText
              :content="optionName(option)"
              :format="element.option_format"
              preset="inline"
            />
          </ABCheckbox>
        </template>
        <template v-else>
          <ABRadio
            v-for="option in optionsResolved"
            :key="option.id"
            :read-only="isEditMode"
            :error="displayFormDataError"
            :model-value="option.value === inputValue"
            @update:model-value="onOptionChange(option, $event)"
          >
            <FormattedText
              :content="optionName(option)"
              :format="element.option_format"
              preset="inline"
            />
          </ABRadio>
        </template>
      </template>
      <template v-else>{{ $t('choiceElement.addOptions') }}</template>
    </template>
  </ABFormGroup>
</template>

<script>
import formElement from '@baserow/modules/builder/mixins/formElement'
import { ensureString } from '@baserow/modules/core/utils/validator'
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import FormattedText from '@baserow/modules/builder/components/FormattedText'

export default {
  name: 'ChoiceElement',
  components: { FormattedText },
  mixins: [formElement],
  props: {
    /**
     * @type {Object}
     * @property {string} label - The label displayed above the choice element
     * @property {string} default_value - The default value selected
     * @property {string} placeholder - The placeholder value of the choice element
     * @property {boolean} required - If the element is required for form submission
     * @property {boolean} multiple - If the choice element allows multiple selections
     * @property {boolean} show_as_dropdown - If the choice element should be displayed as a dropdown
     * @property {Array} options - The options of the choice element
     * @property {string} option_type - The type of the options
     * @property {string} option_format - The format (plain/markdown) of the option names
     * @property {string} formula_name - The expression for the name of the option
     * @property {string} formula_value - The expression for the value of the option
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    labelResolved() {
      return ensureString(this.resolveFormula(this.element.label))
    },
    placeholderResolved() {
      return ensureString(this.resolveFormula(this.element.placeholder))
    },
    canHaveOptions() {
      return !this.elementIsInError
    },
    optionsResolved() {
      return this.elementType.getOptionsResolved(
        this.element,
        this.applicationContext
      )
    },
    hasMarkdownOptions() {
      return this.element.option_format === TEXT_FORMAT_TYPES.MARKDOWN
    },
    /**
     * The names of the selected options, in the order the values are stored,
     * used to render the collapsed dropdown when the options are Markdown.
     */
    selectedOptionNames() {
      const values = this.element.multiple
        ? this.inputValue || []
        : [this.inputValue]
      return values
        .map((value) =>
          this.optionsResolved.find((option) => option.value === value)
        )
        .filter(Boolean)
        .map((option) => this.dropdownOptionName(option))
    },
  },
  watch: {
    'element.multiple'() {
      this.setFormData(this.resolvedDefaultValue)
    },
  },
  methods: {
    optionName(option) {
      return ensureString(option.name || option.value)
    },
    dropdownOptionName(option) {
      return option.name || (option.value ? `${option.value}` : '')
    },
    onOptionChange(option, value) {
      if (value) {
        if (this.element.multiple) {
          this.inputValue = [...this.inputValue, option.value]
        } else {
          this.inputValue = option.value
        }
      } else if (this.element.multiple) {
        this.inputValue = this.inputValue.filter((v) => v !== option.value)
      }
    },
  },
}
</script>

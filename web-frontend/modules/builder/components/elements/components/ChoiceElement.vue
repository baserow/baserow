<template>
  <ABFormGroup
    :label="labelResolved"
    :label-format="element.label?.format"
    :required="element.required"
    :error-message="displayFormDataError ? $t('error.requiredField') : ''"
    :style="getStyleOverride('input')"
  >
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
      <!--
      -- The selected option(s) are rendered here rather than by the dropdown
      -- itself, so that a markdown name doesn't show its raw syntax once
      -- selected.
      -->
      <template #value>
        <span class="ab-dropdown__selected-text">
          <template
            v-for="(option, index) in selectedOptions"
            :key="`${index}-${option.value}`"
          >
            <template v-if="index > 0">, </template>
            <ABFormattedText
              :value="optionLabel(option)"
              :format="option.nameFormat"
              profile="inline"
              :allow-links="false"
            />
          </template>
        </span>
      </template>
      <ABDropdownItem
        v-for="option in optionsResolved"
        :key="option.id"
        :name="optionLabel(option)"
        :value="option.value"
      >
        <ABFormattedText
          :value="optionLabel(option)"
          :format="option.nameFormat"
          profile="inline"
          :allow-links="false"
        />
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
            <ABFormattedText
              :value="optionLabel(option)"
              :format="option.nameFormat"
              profile="inline"
              :allow-links="false"
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
            <ABFormattedText
              :value="optionLabel(option)"
              :format="option.nameFormat"
              profile="inline"
              :allow-links="false"
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

export default {
  name: 'ChoiceElement',
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
     * @property {Object} formula_name - The formula for the name of the options
     * @property {Object} formula_value - The formula for the value of the options
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
    /**
     * The resolved options matching the current value(s), for the closed
     * dropdown.
     */
    selectedOptions() {
      const selectedValues = Array.isArray(this.inputValue)
        ? this.inputValue
        : [this.inputValue]
      return this.optionsResolved.filter((option) =>
        selectedValues.includes(option.value)
      )
    },
  },
  watch: {
    'element.multiple'() {
      this.setFormData(this.resolvedDefaultValue)
    },
  },
  methods: {
    /**
     * The text shown for an option: its resolved name, or its value when the
     * name is empty.
     */
    optionLabel(option) {
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

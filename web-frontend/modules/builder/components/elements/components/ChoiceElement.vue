<template>
  <ABFormGroup
    :label="labelResolved"
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
      @hide="onFormElementTouch"
    >
      <ABDropdownItem
        v-for="option in optionsResolved"
        :key="option.id"
        :name="option.name || (option.value ? `${option.value}` : '')"
        :value="option.value"
      />
    </ABDropdown>
    <template v-else>
      <template v-if="canHaveOptions">
        <template v-if="element.multiple">
          <ABCheckbox
            v-for="option in optionsResolved"
            :key="option.id"
            :read-only="isEditMode"
            :error="displayFormDataError"
            :value="inputValue.includes(option.value)"
            @input="onOptionChange(option, $event)"
          >
            {{ option.name || option.value }}
          </ABCheckbox>
        </template>
        <template v-else>
          <ABRadio
            v-for="option in optionsResolved"
            :key="option.id"
            :read-only="isEditMode"
            :error="displayFormDataError"
            :value="option.value === inputValue"
            @input="onOptionChange(option, $event)"
          >
            {{ option.name || option.value }}
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
     * @property {string} formula_name - The formula for the name of the option
     * @property {string} formula_value - The formula for the value of the option
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
  },
  watch: {
    'element.multiple'() {
      this.setFormData(this.resolvedDefaultValue)
    },
  },
  methods: {
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

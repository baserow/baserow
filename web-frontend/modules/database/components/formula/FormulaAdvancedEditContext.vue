<template>
  <Context ref="context" max-height-if-outside-viewport class="formula-field">
    <div class="formula-field__input">
      <FormTextarea
        ref="textAreaFormulaInput"
        :value="formula"
        class="auto-expandable-textarea--input-formula"
        :placeholder="
          $t('formulaAdvancedEditContext.textAreaFormulaInputPlaceholder')
        "
        auto-expandable
        @input="formulaChanged"
        @blur="$emit('blur', $event)"
        @click="recalcAutoComplete"
        @keyup="recalcAutoComplete"
        @keydown.tab="doAutoCompleteAfterTab"
        @keydown.enter.exact.prevent="
          ($refs.context.hide(), $emit('hidden', $event))
        "
      />
    </div>
    <div v-if="error" class="formula-field__input-error">{{ error }}</div>
    <div class="formula-field__body">
      <div class="formula-field__items">
        <FormulaFieldItemGroup
          :filtered-items="filteredFields"
          :unfiltered-items="fields"
          :title="$t('formulaAdvancedEditContext.fields')"
          @hover-item="selectItem"
          @click-item="doAutoComplete(null, $event)"
        />
        <FormulaFieldItemGroup
          :filtered-items="filteredFunctions"
          :unfiltered-items="functions"
          :title="$t('formulaAdvancedEditContext.functions')"
          @hover-item="selectItem"
          @click-item="doAutoComplete($event, null)"
        />
        <FormulaFieldItemGroup
          :filtered-items="filteredOperators"
          :unfiltered-items="unfilteredOperators"
          :title="$t('formulaAdvancedEditContext.operators')"
          :show-operator="true"
          @hover-item="selectItem"
          @click-item="doAutoComplete($event, null)"
        />
      </div>
      <FormulaFieldItemDescription :selected-item="selectedItem" />
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

import {
  autocompleteFormula,
  calculateFilteredFunctionsAndFieldsBasedOnCursorLocation,
} from '@baserow/modules/core/formula/autocompleter/formulaAutocompleter'
import FormulaFieldItemGroup from '@baserow/modules/database/components/formula/FormulaFieldItemGroup'
import FormulaFieldItemDescription from '@baserow/modules/database/components/formula/FormulaFieldItemDescription'

export default {
  name: 'FormulaAdvancedEditContext',
  components: {
    FormulaFieldItemDescription,
    FormulaFieldItemGroup,
  },
  mixins: [context],
  props: {
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    modelValue: {
      type: String,
      required: true,
    },
    error: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['blur', 'hidden', 'update:modelValue'],
  data() {
    return {
      selectedItem: null,
      filteredFunctions: [],
      filteredFields: [],
    }
  },
  computed: {
    functions() {
      return Object.values(this.$registry.getAll('formula_function'))
        .sort(this.sortFunctions.bind(this))
        .map((f) =>
          this.wrapItem(
            f.getType(),
            this.funcTypeToIconClass(f),
            f.getDescription(),
            f.getExamples(),
            f.getSyntaxUsage(),
            f.getOperator(),
            f
          )
        )
    },
    formula: {
      get() {
        return this.modelValue
      },
      set(value) {
        this.$emit('update:modelValue', value)
      },
    },
    fieldItems() {
      return this.fields.map((f) =>
        this.wrapItem(
          f.name,
          this.getFieldIcon(f),
          this.$t('formulaAdvancedEditContext.fieldType', { type: f.type }),
          [`concat(field('${f.name}'), ' extra text ')`],
          [`field('${f.name}')`],
          false,
          f
        )
      )
    },
    unfilteredOperators() {
      return this.functions.filter((f) => f.operator)
    },
    filteredOperators() {
      return this.filteredFunctions.filter((f) => f.operator)
    },
  },
  watch: {
    functions() {
      this.selectedItem = this.functions[0]
      this.recalcAutoComplete()
    },
  },
  mounted() {
    this.selectedItem = this.functions[0]
    this.recalcAutoComplete()
  },
  methods: {
    formulaChanged(newFormula) {
      this.formula = newFormula
    },
    getFieldIcon(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.getIconClass()
    },
    funcTypeToIconClass(func) {
      const formulaTypeValue = func.getFormulaType()
      const formulaType = this.$registry.get('formula_type', formulaTypeValue)
      return formulaType.getIconClass()
    },
    resetFilters() {
      this.filteredFunctions = this.functions
      this.filteredFields = this.fieldItems
    },
    selectItem(item) {
      this.selectedItem = item
    },
    recalcAutoComplete(event) {
      // Prevent tabs from doing anything as doAutocomplete will handle a tab instead.
      if (event && event.key === 'Tab') {
        event.preventDefault()
        return
      }
      const cursorLocation =
        this.$refs.textAreaFormulaInput !== undefined
          ? this.$refs.textAreaFormulaInput.$refs.textarea.selectionStart
          : 0

      const { filteredFields, filteredFunctions, filtered } =
        calculateFilteredFunctionsAndFieldsBasedOnCursorLocation(
          this.formula,
          cursorLocation,
          this.fieldItems,
          this.functions
        )

      this.filteredFunctions = filteredFunctions
      this.filteredFields = filteredFields

      if (filtered) {
        if (this.filteredFunctions.length > 0) {
          this.selectItem(filteredFunctions[0])
        } else if (this.filteredFields.length > 0) {
          this.selectItem(filteredFields[0])
        }
      }
      return true
    },
    doAutoCompleteAfterTab(event) {
      // Prevent tabs from doing anything
      if (event && event.key === 'Tab') {
        event.preventDefault()
      }
      this.doAutoComplete(this.filteredFunctions[0], this.filteredFields[0])
    },
    doAutoComplete(functionCandidate, fieldCandidate) {
      const startingCursorLocation =
        this.$refs.textAreaFormulaInput.$refs.textarea.selectionStart

      const { autocompletedFormula, newCursorPosition } = autocompleteFormula(
        this.formula,
        startingCursorLocation,
        functionCandidate,
        fieldCandidate
      )
      this.formula = autocompletedFormula

      this.$nextTick(() => {
        this.$refs.textAreaFormulaInput.$refs.textarea.focus()
        this.$refs.textAreaFormulaInput.$refs.textarea.setSelectionRange(
          newCursorPosition,
          newCursorPosition
        )
        this.recalcAutoComplete()
      })
    },
    async openContext(triggeringEl) {
      await this.$refs.context.show(
        triggeringEl,
        'top',
        'left',
        -triggeringEl.scrollHeight - 3,
        -1
      )
      this.$nextTick(() => {
        this.$refs.textAreaFormulaInput.$refs.textarea.focus()
        this.$refs.textAreaFormulaInput.$refs.textarea.setSelectionRange(
          triggeringEl.selectionStart,
          triggeringEl.selectionEnd
        )
      })
    },
    wrapItem(value, icon, description, examples, syntaxUsage, operator, item) {
      return {
        value,
        icon,
        description,
        examples,
        syntaxUsage,
        operator,
        item,
      }
    },
    sortFunctions(a, b) {
      const aTypeSort = this.$registry
        .get('formula_type', a.getFormulaType())
        .getSortOrder()
      const bTypeSort = this.$registry
        .get('formula_type', b.getFormulaType())
        .getSortOrder()
      const nameA = `${aTypeSort}_${a.getType()}`
      const nameB = `${bTypeSort}_${b.getType()}`
      if (nameA < nameB) {
        return -1
      }
      if (nameA > nameB) {
        return 1
      }

      return 0
    },
  },
}
</script>

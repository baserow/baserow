<template>
  <div>
    <InjectedFormulaInput
      v-if="isFormula"
      v-model="fieldValue"
      :disabled="!fieldMapping.enabled"
      v-bind="$attrs"
    />
    <input
      v-else
      v-model="fieldValue"
      type="text"
      class="form-input"
      :disabled="!fieldMapping.enabled"
      v-bind="$attrs"
    />

    <div class="margin-top-1">
      <label class="checkbox">
        <input
          type="checkbox"
          :checked="isFormula"
          :disabled="!fieldMapping.enabled"
          @change="onToggleFormula($event)"
        />
        <span>Value is Formula</span>
      </label>
    </div>
  </div>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'FieldMapping',
  components: { InjectedFormulaInput },
  props: {
    fieldMapping: {
      type: Object,
      required: true,
    },
  },
  computed: {
    fieldValue: {
      get() {
        return this.fieldMapping.value
      },
      set(value) {
        this.$emit('change', { value })
      },
    },
    isFormula() {
      return this.fieldMapping.value_is_formula !== false
    },
  },
  methods: {
    onToggleFormula(e) {
      const valueIsFormula = e.target.checked
      let value = this.fieldMapping.value ?? ''

      // Reset the value when switching b/w formula and literal
      value = ''

      this.$emit('change', { value_is_formula: valueIsFormula, value })
    },
  },
}
</script>

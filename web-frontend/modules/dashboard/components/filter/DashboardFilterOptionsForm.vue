<template>
  <div>
    <FormGroup
      :label="$t('dashboardFilter.optionValue')"
      :helper-text="$t('dashboardFilter.sourceOptionsHelp')"
      small-label
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        :model-value="filter.formula_value || {}"
        :disabled="disabled"
        placeholder=""
        @update:model-value="$emit('save', { formula_value: $event })"
      />
    </FormGroup>
  </div>
</template>

<script setup>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

defineProps({
  filter: { type: Object, required: true },
  disabled: Boolean,
})
defineEmits(['save'])
</script>

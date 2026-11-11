<template>
  <FormGroup
    :label="$t('agent.instructions')"
    :error="Boolean(errors.instructions)"
    :error-message="
      sectionType.getFieldErrorMessage('instructions', errors.instructions)
    "
    :helper-text="$t('agent.instructionsHelper')"
    small-label
    required
  >
    <FormTextarea
      ref="instructionsInput"
      :model-value="configuration.instructions || ''"
      :error="Boolean(errors.instructions)"
      :disabled="!editable"
      :rows="10"
      :maxlength="100000"
      @update:model-value="$emit('change', { instructions: $event })"
      @blur="$emit('flush')"
    />
  </FormGroup>
</template>

<script setup>
import { ref } from 'vue'

defineOptions({ inheritAttrs: false })
defineProps({
  configuration: { type: Object, required: true },
  errors: { type: Object, required: true },
  sectionType: { type: Object, required: true },
  editable: Boolean,
})
defineEmits(['change', 'flush'])
const instructionsInput = ref(null)

function focusField() {
  instructionsInput.value?.focus()
}

defineExpose({ focusField })
</script>

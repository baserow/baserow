<template>
  <FormGroup :label="$t('agent.name')" small-label required>
    <FormInput
      ref="nameInput"
      :model-value="modelValue.name"
      :placeholder="$t('agent.setupNamePlaceholder')"
      @update:model-value="update({ name: $event })"
    />
  </FormGroup>
  <FormGroup
    class="margin-top-2"
    :label="$t('agent.setupWhatShouldItDo')"
    small-label
    required
  >
    <FormTextarea
      :model-value="modelValue.instructions"
      :placeholder="$t('agent.setupInstructionsPlaceholder')"
      :rows="5"
      @update:model-value="update({ instructions: $event })"
    />
  </FormGroup>
  <div class="agent-create__suggestions">
    <button
      v-for="suggestion in SETUP_SUGGESTIONS"
      :key="suggestion.labelKey"
      type="button"
      class="agent-create__suggestion"
      @click="
        update({
          name: $t(suggestion.nameKey),
          instructions: $t(suggestion.instructionsKey),
        })
      "
    >
      <i class="agent-create__suggestion-icon" :class="suggestion.icon"></i>
      {{ $t(suggestion.labelKey) }}
    </button>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { SETUP_SUGGESTIONS } from '@baserow/modules/agent/utils/agentSetup'

const props = defineProps({
  modelValue: { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue'])
const nameInput = ref(null)

function update(values) {
  emit('update:modelValue', { ...props.modelValue, ...values })
}

onMounted(async () => {
  await nextTick()
  nameInput.value?.focus()
})
</script>

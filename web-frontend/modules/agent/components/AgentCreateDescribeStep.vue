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
      @click="update(suggestionSetup(suggestion, t, offeredActionTypes))"
    >
      <i class="agent-create__suggestion-icon" :class="suggestion.icon"></i>
      {{ $t(suggestion.labelKey) }}
    </button>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  SETUP_SUGGESTIONS,
  setupActionTypes,
  suggestionSetup,
} from '@baserow/modules/agent/utils/agentSetup'

const props = defineProps({
  modelValue: { type: Object, required: true },
  workspace: { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const { $registry } = useNuxtApp()
const nameInput = ref(null)
const offeredActionTypes = computed(() =>
  setupActionTypes($registry, props.workspace).map((type) => type.getType())
)

function update(values) {
  emit('update:modelValue', { ...props.modelValue, ...values })
}

onMounted(async () => {
  await nextTick()
  nameInput.value?.focus()
})
</script>

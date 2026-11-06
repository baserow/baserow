<template>
  <FormGroup
    :label="$t('agent.name')"
    :error="!name.trim()"
    :error-message="name.trim() ? '' : $t('error.requiredField')"
    small-label
    required
  >
    <FormInput
      :model-value="name"
      :error="!name.trim()"
      :disabled="!editable"
      :maxlength="160"
      @update:model-value="$emit('update:name', $event)"
      @blur="$emit('rename')"
    />
  </FormGroup>
  <FormGroup
    class="margin-top-2"
    :label="$t('agent.provider')"
    :error="Boolean(errors.provider_type)"
    :error-message="
      sectionType.getFieldErrorMessage('provider_type', errors.provider_type)
    "
    small-label
    required
  >
    <Dropdown
      ref="providerInput"
      :model-value="configuration.provider_type"
      :error="Boolean(errors.provider_type)"
      :disabled="!editable || availabilityLoading"
      :placeholder="$t('action.makeChoice')"
      :show-search="false"
      fixed-items
      @update:model-value="changeProvider"
    >
      <DropdownItem
        v-for="provider in providers"
        :key="provider.type"
        :value="provider.type"
        :name="provider.name"
        :disabled="!enabledModels[provider.type]?.length"
      />
    </Dropdown>
  </FormGroup>
  <FormGroup
    class="margin-top-2"
    :label="$t('agent.model')"
    :error="Boolean(errors.model_identifier)"
    :error-message="
      sectionType.getFieldErrorMessage(
        'model_identifier',
        errors.model_identifier
      )
    "
    small-label
    required
  >
    <Dropdown
      ref="modelInput"
      :model-value="configuration.model_identifier"
      :error="Boolean(errors.model_identifier)"
      :disabled="
        !editable || availabilityLoading || !configuration.provider_type
      "
      :placeholder="$t('action.makeChoice')"
      fixed-items
      @update:model-value="changeModel"
    >
      <DropdownItem
        v-for="model in models"
        :key="model"
        :value="model"
        :name="model"
        :disabled="!availableModels.includes(model)"
      />
    </Dropdown>
  </FormGroup>
  <FormGroup
    class="margin-top-2"
    :label="$t('agent.reasoningEffort')"
    :helper-text="$t('agent.reasoningEffortDescription')"
    small-label
  >
    <Dropdown
      :model-value="configuration.reasoning_effort || DEFAULT_REASONING_EFFORT"
      :disabled="!editable"
      :show-search="false"
      fixed-items
      @update:model-value="changeReasoningEffort"
    >
      <DropdownItem
        v-for="effort in reasoningEfforts"
        :key="effort.value"
        :value="effort.value"
        :name="effort.name"
      />
    </Dropdown>
  </FormGroup>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { REASONING_EFFORTS } from '@baserow/modules/agent/constants'

const props = defineProps({
  name: { type: String, required: true },
  configuration: { type: Object, required: true },
  errors: { type: Object, required: true },
  enabledModels: { type: Object, required: true },
  sectionType: { type: Object, required: true },
  editable: Boolean,
  availabilityLoading: Boolean,
})
const emit = defineEmits(['update:name', 'rename', 'change', 'flush'])
const { $registry } = useNuxtApp()
const { t } = useI18n()
// The dropdown needs a value for the default, which is saved as null.
const DEFAULT_REASONING_EFFORT = 'default'
const REASONING_EFFORT_LABELS = {
  off: 'agent.reasoningEffortOff',
  low: 'agent.reasoningEffortLow',
  medium: 'agent.reasoningEffortMedium',
  high: 'agent.reasoningEffortHigh',
}
const reasoningEfforts = computed(() => [
  {
    value: DEFAULT_REASONING_EFFORT,
    name: t('agent.reasoningEffortDefault'),
  },
  ...REASONING_EFFORTS.map((effort) => ({
    value: effort,
    name: t(REASONING_EFFORT_LABELS[effort]),
  })),
])
const providerInput = ref(null)
const modelInput = ref(null)
const providers = computed(() => {
  const types = Object.keys(props.enabledModels).filter(
    (type) => props.enabledModels[type].length > 0
  )
  if (props.configuration.provider_type)
    types.push(props.configuration.provider_type)
  const registryTypes = $registry.getAll('generativeAIModel')
  return [...new Set(types)].map((type) => ({
    type,
    name: registryTypes[type]?.getName() || type,
  }))
})
const availableModels = computed(
  () => props.enabledModels[props.configuration.provider_type] || []
)
const models = computed(() =>
  [
    ...new Set([
      ...availableModels.value,
      props.configuration.model_identifier,
    ]),
  ].filter(Boolean)
)

function changeProvider(providerType) {
  if (providerType === props.configuration.provider_type) return
  emit('change', { provider_type: providerType, model_identifier: null })
  emit('flush')
}

function changeModel(model) {
  emit('change', { model_identifier: model })
  emit('flush')
}

function changeReasoningEffort(value) {
  const effort = value === DEFAULT_REASONING_EFFORT ? null : value
  if (effort === props.configuration.reasoning_effort) return
  emit('change', { reasoning_effort: effort })
  emit('flush')
}

function focusField(field) {
  const input = {
    provider_type: providerInput,
    model_identifier: modelInput,
  }[field]?.value
  if (input?.focus) input.focus()
  else input?.$el?.focus()
}

defineExpose({ focusField })
</script>

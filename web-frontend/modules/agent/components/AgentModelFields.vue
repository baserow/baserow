<template>
  <FormGroup
    v-bind="$attrs"
    :label="$t('agent.provider')"
    :error="Boolean(errorMessages.provider_type)"
    :error-message="errorMessages.provider_type"
    small-label
    required
  >
    <Dropdown
      ref="providerInput"
      :model-value="values.provider_type"
      :error="Boolean(errorMessages.provider_type)"
      :disabled="disabled || availabilityLoading"
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
    :error="Boolean(errorMessages.model_identifier)"
    :error-message="errorMessages.model_identifier"
    small-label
    required
  >
    <Dropdown
      ref="modelInput"
      :model-value="values.model_identifier"
      :error="Boolean(errorMessages.model_identifier)"
      :disabled="disabled || availabilityLoading || !values.provider_type"
      :placeholder="$t('action.makeChoice')"
      fixed-items
      @update:model-value="$emit('change', { model_identifier: $event })"
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
    <template v-if="reasoningEffortNote" #warning>
      {{ reasoningEffortNote }}
    </template>
    <Dropdown
      :model-value="selectedReasoningEffort"
      :disabled="disabled"
      :show-search="false"
      fixed-items
      @update:model-value="changeReasoningEffort"
    >
      <DropdownItem
        v-for="effort in reasoningEfforts"
        :key="effort.value ?? 'default'"
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

/** The provider, model and reasoning effort of an agent, saved by the host. */
defineOptions({ inheritAttrs: false })
const props = defineProps({
  values: { type: Object, required: true },
  enabledModels: { type: Object, required: true },
  errorMessages: { type: Object, default: () => ({}) },
  disabled: Boolean,
  availabilityLoading: Boolean,
})
const emit = defineEmits(['change'])
const { $registry } = useNuxtApp()
const { t } = useI18n()
const reasoningEfforts = computed(() => [
  { value: null, name: t('agent.reasoningEffortDefault') },
  ...REASONING_EFFORTS.map(({ value, label }) => ({ value, name: t(label) })),
])
const effortName = (effort) =>
  reasoningEfforts.value.find(({ value }) => value === effort)?.name
// Replies use the model's default for a value this version doesn't know.
const selectedReasoningEffort = computed(() =>
  effortName(props.values.reasoning_effort)
    ? props.values.reasoning_effort
    : null
)
// The applied effort is undefined until the server resolved the latest choice.
const reasoningEffortNote = computed(() => {
  const effort = selectedReasoningEffort.value
  const applied = props.values.applied_reasoning_effort
  if (
    effort === null ||
    applied === undefined ||
    applied === effort ||
    props.errorMessages.provider_type ||
    props.errorMessages.model_identifier
  )
    return ''
  const names = {
    model: props.values.model_identifier,
    effort: effortName(effort),
  }
  if (applied === null) return t('agent.reasoningEffortNotSupported', names)
  return t('agent.reasoningEffortAdjusted', {
    ...names,
    applied: effortName(applied),
  })
})
const providerInput = ref(null)
const modelInput = ref(null)
const providers = computed(() => {
  const types = Object.keys(props.enabledModels).filter(
    (type) => props.enabledModels[type].length > 0
  )
  if (props.values.provider_type) types.push(props.values.provider_type)
  const registryTypes = $registry.getAll('generativeAIModel')
  return [...new Set(types)].map((type) => ({
    type,
    name: registryTypes[type]?.getName() || type,
  }))
})
const availableModels = computed(
  () => props.enabledModels[props.values.provider_type] || []
)
const models = computed(() =>
  [
    ...new Set([...availableModels.value, props.values.model_identifier]),
  ].filter(Boolean)
)

function changeProvider(providerType) {
  if (providerType === props.values.provider_type) return
  emit('change', { provider_type: providerType, model_identifier: null })
}

function changeReasoningEffort(effort) {
  if (effort === props.values.reasoning_effort) return
  emit('change', { reasoning_effort: effort })
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

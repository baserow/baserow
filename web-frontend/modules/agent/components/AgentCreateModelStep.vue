<template>
  <p class="agent-create__intro">{{ $t('agent.setupModelIntro') }}</p>
  <AgentModelFields
    :values="modelValues"
    :enabled-models="enabledModels"
    :error-messages="errorMessages"
    @change="changeModel"
  />
  <AgentWebSearchSetting
    class="agent-create__section"
    :configuration="webSearchConfiguration"
    editable
    @change="update({ webSearch: $event })"
  />
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AgentModelFields from '@baserow/modules/agent/components/AgentModelFields'
import AgentWebSearchSetting from '@baserow/modules/agent/components/configuration/AgentWebSearchSetting'
import {
  SETUP_ACTS_AS,
  setupEnabledModels,
  setupTools,
} from '@baserow/modules/agent/utils/agentSetup'

const SETUP_FIELDS = {
  provider_type: 'providerType',
  model_identifier: 'modelIdentifier',
  reasoning_effort: 'reasoningEffort',
}

const props = defineProps({
  modelValue: { type: Object, required: true },
  workspace: { type: Object, required: true },
  availableTools: { type: Array, required: true },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const enabledModels = computed(() => setupEnabledModels(props.workspace))
const modelValues = computed(() =>
  Object.fromEntries(
    Object.entries(SETUP_FIELDS).map(([field, key]) => [
      field,
      props.modelValue[key],
    ])
  )
)
const errorMessages = computed(() =>
  props.modelValue.providerType && !props.modelValue.modelIdentifier
    ? { model_identifier: t('error.requiredField') }
    : {}
)
const hasIdentity = computed(
  () => props.modelValue.actsAs.kind !== SETUP_ACTS_AS.NONE
)
// Whether a model can search is only known once saved, so the switch stays usable.
const webSearchConfiguration = computed(() => ({
  ...modelValues.value,
  web_search_enabled: props.modelValue.webSearch,
  web_search_available: true,
  web_search_blocked_by_tools: false,
  run_as: hasIdentity.value ? props.modelValue.actsAs : null,
  allowed_tools: hasIdentity.value
    ? setupTools(props.modelValue, props.availableTools).allowed_tools
    : [],
}))

function update(values) {
  emit('update:modelValue', { ...props.modelValue, ...values })
}

function changeModel(values) {
  update(
    Object.fromEntries(
      Object.entries(values).map(([field, value]) => [
        SETUP_FIELDS[field],
        value,
      ])
    )
  )
}
</script>

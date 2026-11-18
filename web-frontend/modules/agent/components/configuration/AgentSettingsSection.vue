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
  <AgentModelFields
    ref="modelFields"
    class="margin-top-2"
    :values="configuration"
    :enabled-models="enabledModels"
    :error-messages="errorMessages"
    :disabled="!editable"
    :availability-loading="availabilityLoading"
    @change="changeModelFields"
  />
  <AgentWebSearchSetting
    class="margin-top-3"
    :configuration="configuration"
    :editable="editable"
    @change="changeWebSearch"
  />
  <AgentWebFetchSetting
    class="margin-top-3"
    :configuration="configuration"
    :editable="editable"
    @change="changeWebFetch"
  />
</template>

<script setup>
import { computed, ref } from 'vue'
import AgentModelFields from '@baserow/modules/agent/components/AgentModelFields'
import AgentWebSearchSetting from '@baserow/modules/agent/components/configuration/AgentWebSearchSetting'
import AgentWebFetchSetting from '@baserow/modules/agent/components/configuration/AgentWebFetchSetting'

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
const modelFields = ref(null)
const errorMessages = computed(() =>
  Object.fromEntries(
    ['provider_type', 'model_identifier'].map((field) => [
      field,
      props.sectionType.getFieldErrorMessage(field, props.errors[field]),
    ])
  )
)

function changeModelFields(values) {
  emit('change', values)
  emit('flush')
}

function changeWebSearch(enabled) {
  emit('change', { web_search_enabled: enabled })
  emit('flush')
}

function changeWebFetch(enabled) {
  emit('change', { web_fetch_enabled: enabled })
  emit('flush')
}

const focusField = (field) => modelFields.value?.focusField(field)

defineExpose({ focusField })
</script>

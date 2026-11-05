<template>
  <div class="agent-web-search">
    <div class="agent-web-search__head">
      <div>
        <div class="agent-web-search__title">{{ $t('agent.webSearch') }}</div>
        <div class="agent-web-search__description">
          {{ $t('agent.webSearchDescription') }}
        </div>
      </div>
      <SwitchInput
        class="agent-web-search__switch"
        small
        :model-value="configuration.web_search_enabled"
        :disabled="!canChange"
        :aria-label="$t('agent.webSearch')"
        @update:model-value="$emit('change', $event)"
      />
    </div>
    <div v-if="!available && modelChosen" class="agent-web-search__unavailable">
      {{
        configuration.web_search_blocked_by_tools
          ? $t('agent.webSearchBlockedByTools')
          : configuration.web_search_enabled
            ? $t('agent.webSearchUnavailableWhileOn')
            : $t('agent.webSearchUnavailable')
      }}
    </div>
    <Alert v-else-if="reachesWorkspace" type="warning" class="margin-top-1">
      {{ $t('agent.webSearchWorkspaceWarning') }}
    </Alert>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  configuration: { type: Object, required: true },
  editable: Boolean,
})
defineEmits(['change'])

const available = computed(() => props.configuration.web_search_available)
const modelChosen = computed(() =>
  Boolean(
    props.configuration.provider_type && props.configuration.model_identifier
  )
)
// A setting saved on an unsupported model can still be turned off.
const canChange = computed(
  () =>
    props.editable &&
    (available.value || props.configuration.web_search_enabled)
)
const reachesWorkspace = computed(
  () =>
    available.value &&
    props.configuration.web_search_enabled &&
    Boolean(props.configuration.run_as) &&
    props.configuration.allowed_tools.length > 0
)
</script>

<template>
  <div class="agent-web-search">
    <div class="agent-web-search__head">
      <div>
        <div class="agent-web-search__title">{{ $t('agent.webFetch') }}</div>
        <div class="agent-web-search__description">
          {{ $t('agent.webFetchDescription') }}
        </div>
      </div>
      <div class="agent-web-search__controls">
        <SwitchInput
          class="agent-web-search__switch"
          small
          :model-value="configuration.web_fetch_enabled"
          :disabled="!editable"
          :aria-label="$t('agent.webFetch')"
          @update:model-value="$emit('change', $event)"
        />
      </div>
    </div>
    <Alert v-if="reachesWorkspace" type="warning" class="margin-top-1">
      {{ $t('agent.webFetchWorkspaceWarning') }}
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

const reachesWorkspace = computed(
  () =>
    props.configuration.web_fetch_enabled &&
    Boolean(props.configuration.run_as) &&
    props.configuration.allowed_tools.length > 0
)
</script>

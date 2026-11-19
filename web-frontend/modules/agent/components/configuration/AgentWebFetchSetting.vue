<template>
  <div class="agent-web-setting">
    <div class="agent-web-setting__head">
      <div>
        <div class="agent-web-setting__title">{{ $t('agent.webFetch') }}</div>
        <div class="agent-web-setting__description">
          {{ $t('agent.webFetchDescription') }}
        </div>
      </div>
      <div class="agent-web-setting__controls">
        <SwitchInput
          class="agent-web-setting__switch"
          small
          :model-value="configuration.web_fetch_enabled"
          :disabled="!editable"
          :aria-label="$t('agent.webFetch')"
          @update:model-value="$emit('change', $event)"
        />
      </div>
    </div>
    <Alert
      v-if="configuration.web_fetch_enabled"
      type="warning"
      class="margin-top-1"
    >
      {{ $t('agent.webFetchWarning') }}
    </Alert>
  </div>
</template>

<script setup>
defineProps({
  configuration: { type: Object, required: true },
  editable: Boolean,
})
defineEmits(['change'])
</script>

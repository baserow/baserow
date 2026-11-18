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

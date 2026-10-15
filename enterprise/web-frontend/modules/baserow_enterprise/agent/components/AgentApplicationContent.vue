<template>
  <div class="agent-application">
    <header class="layout__col-2-1 header agent-application__header">
      <div class="agent-application__header-name">{{ agent.name }}</div>
    </header>
    <div class="layout__col-2-2 agent-application__content">
      <div class="agent-application__empty">
        <i class="agent-application__empty-icon baserow-icon-agent"></i>
        <h1 class="agent-application__title">{{ agent.name }}</h1>
        <p class="agent-application__description">
          {{ $t('agent.emptyDescription') }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ agent: { type: Object, required: true } })
</script>

<template>
  <div class="agent-card-list-header">
    <ButtonText
      class="agent-card-list-header__toggle-all"
      type="secondary"
      size="small"
      button-type="button"
      @click="$emit('toggle-all')"
    >
      {{ $t(allExpanded ? 'agent.collapseAll' : 'agent.expandAll') }}
    </ButtonText>
    <span class="agent-card-list-header__label">{{ $t('agent.enabled') }}</span>
  </div>
</template>

<script setup>
import ButtonText from '@baserow/modules/core/components/ButtonText'

defineProps({
  /** Whether every card of the list is expanded. */
  allExpanded: Boolean,
})
defineEmits(['toggle-all'])
</script>

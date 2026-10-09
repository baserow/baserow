<template>
  <div class="agent-builder">
    <header class="layout__col-2-1 header header--space-between">
      <div class="agent-builder__header-name">{{ agentBuilder.name }}</div>
      <Button
        v-if="canCreate"
        type="secondary"
        icon="iconoir-plus"
        @click="createModal.show()"
      >
        {{ $t('agentBuilder.createAgent') }}
      </Button>
    </header>
    <div class="layout__col-2-2 agent-builder__content">
      <div class="agent-builder__empty">
        <i class="agent-builder__empty-icon iconoir-sparks"></i>
        <h1 class="agent-builder__title">
          {{
            selectedAgent ? selectedAgent.name : $t('agentBuilder.emptyTitle')
          }}
        </h1>
        <p class="agent-builder__description">
          {{
            selectedAgent
              ? $t('agentBuilder.agentDescription')
              : $t('agentBuilder.emptyDescription')
          }}
        </p>
        <Button
          v-if="!selectedAgent && canCreate"
          icon="iconoir-plus"
          @click="createModal.show()"
        >
          {{ $t('agentBuilder.createAgent') }}
        </Button>
      </div>
    </div>
    <CreateAgentModal ref="createModal" :agent-builder="agentBuilder" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import CreateAgentModal from '@baserow_enterprise/agentBuilder/components/CreateAgentModal'

const props = defineProps({ agentBuilder: { type: Object, required: true } })
const { $store, $hasPermission } = useNuxtApp()
const createModal = ref(null)
const selectedAgent = computed(() =>
  props.agentBuilder.agents.find(
    ({ id }) => id === $store.getters['agentBuilderAgent/getSelectedId']
  )
)
const canCreate = computed(() =>
  $hasPermission(
    'agent_builder.create_agent',
    props.agentBuilder,
    props.agentBuilder.workspace.id
  )
)
</script>

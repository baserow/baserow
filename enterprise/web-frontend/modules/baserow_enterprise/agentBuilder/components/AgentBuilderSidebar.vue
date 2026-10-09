<template>
  <SidebarApplication
    :workspace="workspace"
    :application="application"
    @selected="selectApplication"
  >
    <template #body>
      <template v-if="selected">
        <ul class="tree__subs">
          <AgentSidebarItem
            v-for="agent in agents"
            :key="agent.id"
            :agent-builder="application"
            :agent="agent"
          />
        </ul>
        <a v-if="canCreate" class="tree__sub-add" @click="createModal.show()">
          <i class="tree__sub-add-icon iconoir-plus"></i>
          {{ $t('agentBuilder.createAgent') }}
        </a>
        <CreateAgentModal ref="createModal" :agent-builder="application" />
      </template>
    </template>
  </SidebarApplication>
</template>

<script setup>
import { computed, ref } from 'vue'
import SidebarApplication from '@baserow/modules/core/components/sidebar/SidebarApplication'
import AgentSidebarItem from '@baserow_enterprise/agentBuilder/components/AgentSidebarItem'
import CreateAgentModal from '@baserow_enterprise/agentBuilder/components/CreateAgentModal'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  application: { type: Object, required: true },
  workspace: { type: Object, required: true },
})
const { $store, $registry, $hasPermission } = useNuxtApp()
const createModal = ref(null)
const selected = computed(() =>
  $store.getters['application/isSelected'](props.application)
)
const agents = computed(() =>
  $store.getters['agentBuilderAgent/getOrdered'](props.application)
)
const canCreate = computed(() =>
  $hasPermission(
    'agent_builder.create_agent',
    props.application,
    props.workspace.id
  )
)

async function selectApplication() {
  try {
    await $registry
      .get('application', 'agent_builder')
      .select(props.application)
  } catch (error) {
    notifyIf(error, 'application')
  }
}
</script>

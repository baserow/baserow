<template>
  <li class="tree__sub" :class="{ active: selected }">
    <NuxtLink class="tree__sub-link" :to="agentRoute" :title="agent.name">
      <Editable
        ref="rename"
        :value="agent.name"
        class="agent-builder__sidebar-name"
        @change="renameAgent"
      />
    </NuxtLink>
    <a
      v-if="canUpdate || canDelete || additionalContextComponents.length"
      class="tree__options"
      :aria-label="$t('agentBuilder.agentOptions')"
      @click="context.toggle($event.currentTarget, 'bottom', 'right', 0)"
      @mousedown.stop
    >
      <i class="baserow-icon-more-vertical"></i>
    </a>
    <Context ref="context" overflow-scroll max-height-if-outside-viewport>
      <div class="context__menu-title">{{ agent.name }} ({{ agent.id }})</div>
      <ul class="context__menu">
        <li
          v-for="(component, index) in additionalContextComponents"
          :key="index"
          class="context__menu-item"
          @click="context.hide()"
        >
          <component
            :is="component"
            :application="agentBuilder"
            :agent-definition="agent"
          />
        </li>
        <li v-if="canUpdate" class="context__menu-item">
          <a class="context__menu-item-link" @click="enableRename">
            <i class="context__menu-item-icon iconoir-edit-pencil"></i>
            {{ $t('action.rename') }}
          </a>
        </li>
        <li
          v-if="canDelete"
          class="context__menu-item context__menu-item--with-separator"
        >
          <a
            class="context__menu-item-link context__menu-item-link--delete"
            :class="{ 'context__menu-item-link--loading': deleting }"
            @click="deleteAgent"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('action.delete') }}
          </a>
        </li>
      </ul>
    </Context>
  </li>
</template>

<script setup>
import { computed, ref } from 'vue'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  agentBuilder: { type: Object, required: true },
  agent: { type: Object, required: true },
})
const { $store, $registry, $hasPermission } = useNuxtApp()
const context = ref(null)
const rename = ref(null)
const deleting = ref(false)
const selected = computed(
  () =>
    $store.getters['application/isSelected'](props.agentBuilder) &&
    $store.getters['agentBuilderAgent/getSelectedId'] === props.agent.id
)
const agentRoute = computed(() => ({
  name: 'agent-builder',
  params: { agentBuilderId: props.agentBuilder.id, agentId: props.agent.id },
}))
const canUpdate = computed(() =>
  $hasPermission(
    'agent_builder_agent.update',
    props.agent,
    props.agentBuilder.workspace.id
  )
)
const canDelete = computed(() =>
  $hasPermission(
    'agent_builder_agent.delete',
    props.agent,
    props.agentBuilder.workspace.id
  )
)
const additionalContextComponents = computed(() =>
  Object.values($registry.getAll('plugin'))
    .flatMap((plugin) =>
      plugin.getAdditionalApplicationChildContextComponents(
        props.agentBuilder.workspace,
        props.agentBuilder,
        props.agent
      )
    )
    .filter(Boolean)
)

function enableRename() {
  context.value.hide()
  rename.value.edit()
}

async function renameAgent(event) {
  try {
    await $store.dispatch('agentBuilderAgent/update', {
      agentBuilder: props.agentBuilder,
      agent: props.agent,
      values: { name: event.value },
    })
  } catch (error) {
    rename.value?.set(event.oldValue)
    notifyIf(error, 'agentBuilderAgent')
  }
}

async function deleteAgent() {
  if (deleting.value) return
  deleting.value = true
  try {
    await $store.dispatch('agentBuilderAgent/delete', {
      agentBuilder: props.agentBuilder,
      agent: props.agent,
    })
    context.value?.hide()
    await $store.dispatch('toast/restore', {
      trash_item_type: 'agent_builder_agent',
      trash_item_id: props.agent.id,
    })
  } catch (error) {
    notifyIf(error, 'agentBuilderAgent')
  } finally {
    deleting.value = false
  }
}
</script>

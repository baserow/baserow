<template>
  <component
    :is="component"
    v-if="component"
    :key="targetKey"
    :workspace="workspace"
    :action="action"
    :parameters="parameters"
    :label="$t('kumaPrompt.' + action)"
    :title="$t('kumaPrompt.' + action)"
    :placeholder="$t('kumaPrompt.' + action + 'Placeholder')"
    @completed="$emit('completed', $event)"
  />
</template>

<script setup>
import { computed } from 'vue'
import { useStore } from 'vuex'

const props = defineProps({
  action: { type: String, required: true },
  workspaceId: { type: Number, required: true },
  parameters: { type: Object, required: true },
})
defineEmits(['completed'])
const store = useStore()
const { $registry } = useNuxtApp()
const workspace = computed(() =>
  store.getters['workspace/get'](props.workspaceId)
)
const component = computed(() => {
  if (!workspace.value) return null
  return Object.values($registry.getAll('plugin'))
    .map((plugin) => plugin.getEditorPromptComponent(workspace.value))
    .find(Boolean)
})
const targetKey = computed(() =>
  JSON.stringify([props.workspaceId, props.action, props.parameters])
)
</script>

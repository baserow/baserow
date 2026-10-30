<template>
  <div
    class="collaborator-avatar"
    :class="{ 'collaborator-avatar--agent': agent }"
  >
    <i v-if="agent" class="baserow-icon-agent" aria-hidden="true"></i>
    <template v-else>{{ name.slice(0, 1).toUpperCase() }}</template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useStore } from 'vuex'
import { getCollaboratorName } from '@baserow/modules/core/utils/collaborator'

const props = defineProps({
  field: { type: Object, default: null },
  collaborator: {
    type: [Object, Number],
    required: true,
  },
})
const store = useStore()
const value = computed(() =>
  typeof props.collaborator === 'number'
    ? { id: props.collaborator }
    : props.collaborator
)
const agent = computed(() => {
  if (value.value.agent) {
    return true
  }
  const collaborator = store.getters['workspace/getCollaboratorById'](
    value.value.id
  )
  if (collaborator) {
    return Boolean(collaborator.agent)
  }
  return Boolean(
    props.field?.available_collaborators?.find(
      (collaborator) => collaborator.id === value.value.id
    )?.agent
  )
})
const name = computed(() => getCollaboratorName(value.value, store) || '')
</script>

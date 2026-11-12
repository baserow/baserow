<template>
  <div
    class="collaborator-avatar"
    :class="{ 'collaborator-avatar--identity': identity }"
  >
    <i v-if="identity" class="iconoir-lock" aria-hidden="true"></i>
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
const identity = computed(() => {
  if (value.value.user_type === 'identity') {
    return true
  }
  const collaborator = store.getters['workspace/getCollaboratorById'](
    value.value.id
  )
  if (collaborator) {
    return collaborator.user_type === 'identity'
  }
  return (
    props.field?.available_collaborators?.find(
      (collaborator) => collaborator.id === value.value.id
    )?.user_type === 'identity'
  )
})
const name = computed(() => getCollaboratorName(value.value, store) || '')
</script>

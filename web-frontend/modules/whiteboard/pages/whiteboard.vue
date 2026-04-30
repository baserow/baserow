<template>
  <div class="whiteboard-app">
    <ExcalidrawCollab
      v-if="whiteboard && contentLoaded"
      :whiteboard="whiteboard"
      :read-only="readOnly"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { useNuxtApp, useAsyncData, useHead } from '#app'

import ExcalidrawCollab from '@baserow/modules/whiteboard/components/ExcalidrawCollab.vue'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'whiteboardLoading',
  ],
})

const store = useStore()
const route = useRoute()
const { $realtime, $hasPermission } = useNuxtApp()

const { data, error: fetchError } = await useAsyncData(
  `whiteboard-data-${route.params.whiteboardId}`,
  async () => {
    const whiteboard = store.getters['application/getSelected']
    const workspace = store.getters['workspace/getSelected']
    return { workspace, whiteboard }
  }
)

if (fetchError.value) {
  throw fetchError.value
}

const whiteboard = computed(() => data.value?.whiteboard)

// True once `fetchInitial` has loaded the content for THIS specific
// whiteboard on the client. We must not render `<ExcalidrawCollab>`
// before this is true: Excalidraw consumes `initialData` only at mount
// time, so any edit made on top of an empty initial scene would queue
// an autosave that PUTs a snapshot built on top of nothing, silently
// wiping the saved content.
//
// `useAsyncData` is not enough on its own — its callback runs only
// during SSR, and on client hydration it just returns the serialized
// payload without re-running. The Vuex store on the client never sees
// any dispatch made inside the callback, so we always trigger the
// fetch from `onMounted` (which runs on the client) and gate the
// child render on the resulting store state.
const contentLoaded = computed(() => {
  const loadedId = store.getters['whiteboardApplication/getWhiteboardId']
  return loadedId != null && loadedId === whiteboard.value?.id
})

// VIEWER and COMMENTER roles only have `whiteboard.read`; EDITOR and
// above also have `whiteboard.update_content`. Drive Excalidraw's
// view-mode and our broadcast/autosave wiring off this single check so
// the editor opens read-only for users who can't modify the scene.
const readOnly = computed(() => {
  if (!whiteboard.value) return true
  return !$hasPermission(
    'whiteboard.update_content',
    whiteboard.value,
    whiteboard.value.workspace.id
  )
})

useHead(() => ({
  title: whiteboard.value?.name || '',
}))

onMounted(async () => {
  if (!whiteboard.value) return
  await store.dispatch('whiteboardApplication/fetchInitial', {
    whiteboardId: whiteboard.value.id,
  })
  $realtime.subscribe('whiteboard', { whiteboard_id: whiteboard.value.id })
})

onBeforeUnmount(() => {
  if (whiteboard.value) {
    $realtime.unsubscribe('whiteboard', { whiteboard_id: whiteboard.value.id })
  }
})
</script>

<style lang="scss" scoped>
.whiteboard-app {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
}
</style>

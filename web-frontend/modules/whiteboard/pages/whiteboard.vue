<template>
  <div class="whiteboard-app">
    <ExcalidrawCollab
      v-if="whiteboard && contentLoaded && workspace"
      :whiteboard="whiteboard"
      :workspace="workspace"
      :read-only="readOnly"
      :can-comment="canComment"
      :can-view-comments="canViewComments"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { useNuxtApp, useAsyncData, useHead } from '#app'

import ExcalidrawCollab from '@baserow/modules/whiteboard/components/ExcalidrawCollab.vue'
import { notifyIf } from '@baserow/modules/core/utils/error'

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
    return { whiteboard }
  }
)

if (fetchError.value) {
  throw fetchError.value
}

const whiteboard = computed(() => data.value?.whiteboard)

// The whiteboard's own workspace, looked up by id rather than relying
// on `workspace/getSelected`. The selected getter changes whenever the
// user navigates between workspaces, and components can latch onto the
// wrong list of users while the selection is in flux. Looking up the
// whiteboard's specific workspace gives a stable, board-scoped object
// that we hand down as a prop to every component that needs it.
const workspace = computed(() => {
  const id = whiteboard.value?.workspace?.id
  if (id == null) return null
  return store.getters['workspace/get'](id) || null
})

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

// COMMENTER + EDITOR + BUILDER + ADMIN can post comments. VIEWERs do
// not see the toolbar at all (and the layer hides too — see
// `canViewComments`).
const canComment = computed(() => {
  if (!whiteboard.value) return false
  return $hasPermission(
    'whiteboard.create_comment',
    whiteboard.value,
    whiteboard.value.workspace.id
  )
})

// COMMENTER and above can list/see comments; VIEWERs cannot. Used to
// gate the entire comment overlay (pins + popups) and to skip the
// initial `fetchAll` that would otherwise 401.
const canViewComments = computed(() => {
  if (!whiteboard.value) return false
  return $hasPermission(
    'whiteboard.list_comments',
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
  // Comments are loaded after the scene; the WS subscription on the
  // whiteboard page also picks up `whiteboard_comment_*` events.
  // VIEWERs lack `whiteboard.list_comments` and would 401 — skip.
  if (canViewComments.value) {
    try {
      await store.dispatch('whiteboardComments/fetchAll', {
        whiteboardId: whiteboard.value.id,
      })
    } catch (error) {
      notifyIf(error, 'application')
    }
  }
  $realtime.subscribe('whiteboard', { whiteboard_id: whiteboard.value.id })

  // Deep-link from a notification: open the targeted thread once the
  // comment list has loaded. We use `?comment=<id>` rather than a hash
  // so the URL stays cleanly bookmarkable.
  if (canViewComments.value) {
    const targetCommentId = parseInt(route.query.comment, 10)
    if (Number.isFinite(targetCommentId)) {
      // The notification can target either a top-level thread or a
      // reply; resolve to the thread root before opening.
      const all = store.getters['whiteboardComments/getComments']
      const target = all.find((c) => c.id === targetCommentId)
      const threadId = target?.parent_comment_id ?? targetCommentId
      if (threadId) {
        store.dispatch('whiteboardComments/openThread', threadId)
      }
    }
  }
})

onBeforeUnmount(() => {
  if (whiteboard.value) {
    $realtime.unsubscribe('whiteboard', { whiteboard_id: whiteboard.value.id })
  }
  store.dispatch('whiteboardComments/reset')
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

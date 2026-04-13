<template>
  <div class="whiteboard-app">
    <div v-if="loading" class="whiteboard-app__loading">
      {{ $t('whiteboardPage.loading') }}
    </div>
    <TldrawEditor
      v-else-if="whiteboard"
      ref="tldrawEditor"
      :whiteboard-id="whiteboard.id"
      :snapshot="content"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useStore } from 'vuex'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { useNuxtApp, useAsyncData, useHead } from '#app'

import TldrawEditor from '@baserow/modules/whiteboard/components/TldrawEditor'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'whiteboardLoading',
  ],
  // Force a full page recreation when the whiteboardId param changes.
  // Without this, Vue reuses the component instance on same-pattern
  // route transitions (e.g. /whiteboard/381 → /whiteboard/382) and
  // lifecycle hooks like onMounted do not fire again.
  key: (route) => `whiteboard-${route.params.whiteboardId}`,
})

const store = useStore()
const route = useRoute()
const { $realtime } = useNuxtApp()

const tldrawEditor = ref(null)

const {
  data,
  pending,
  error: fetchError,
} = await useAsyncData(
  `whiteboard-data-${route.params.whiteboardId}`,
  async () => {
    const whiteboard = store.getters['application/getSelected']
    const workspace = store.getters['workspace/getSelected']
    return {
      workspace,
      whiteboard,
    }
  }
)

if (fetchError.value) {
  throw fetchError.value
}

const whiteboard = computed(() => data.value?.whiteboard)
const workspace = computed(() => data.value?.workspace)
const loading = computed(() => store.getters['whiteboardApplication/isLoading'])
const content = computed(
  () => store.getters['whiteboardApplication/getContent']
)

useHead(() => ({
  title: whiteboard.value?.name || '',
}))

// Save the whiteboard snapshot before navigating away. Unlike
// onBeforeUnmount (which doesn't await async work), the route guard
// waits for the returned promise to resolve before proceeding.
onBeforeRouteLeave(async () => {
  if (tldrawEditor.value?.saveSnapshot) {
    await tldrawEditor.value.saveSnapshot()
  }
})

onMounted(() => {
  if (whiteboard.value) {
    store.dispatch('whiteboardApplication/fetchInitial', {
      whiteboardId: whiteboard.value.id,
    })

    $realtime.subscribe('whiteboard', {
      whiteboard_id: whiteboard.value.id,
    })
  }
})

onBeforeUnmount(() => {
  if (whiteboard.value) {
    $realtime.unsubscribe('whiteboard', {
      whiteboard_id: whiteboard.value.id,
    })
  }
  store.dispatch('whiteboardApplication/reset')
})
</script>

<style>
.whiteboard-app {
  position: relative;
  width: 100%;
  height: 100%;
}

.whiteboard-app__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 16px;
  color: #666;
}
</style>

<template>
  <div ref="container" class="whiteboard__tldraw-container"></div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'
import UserFileService from '@baserow/modules/core/services/userFile'

/**
 * Map a Baserow locale code to the tldraw locale code. Most are identical,
 * but a few need translation (e.g. 'ko' → 'ko-kr').
 */
const BASEROW_TO_TLDRAW_LOCALE = {
  ko: 'ko-kr',
}

function toTldrawLocale(baserowLocale) {
  return BASEROW_TO_TLDRAW_LOCALE[baserowLocale] || baserowLocale
}

export default {
  name: 'TldrawEditor',
  props: {
    whiteboardId: {
      type: Number,
      required: true,
    },
    snapshot: {
      type: Object,
      default: null,
    },
  },
  setup(props) {
    const container = ref(null)
    const store = useStore()
    const { $client } = useNuxtApp()

    let reactRoot = null
    let editorInstance = null
    let tldrawModule = null
    let saveInterval = null
    let isDirty = false
    // Accumulate changes between broadcast flushes.
    let pendingLocalChanges = []
    let broadcastTimer = null

    const pendingRemoteChanges = computed(
      () => store.getters['whiteboardApplication/getPendingRemoteChanges']
    )

    const userLocale = computed(() =>
      toTldrawLocale(store.getters['auth/getLanguage'])
    )

    // Watch for remote changes from other users via WS.
    // The store creates a new array reference on each push so the
    // watcher reliably fires.
    watch(pendingRemoteChanges, (changes) => {
      if (changes.length > 0 && editorInstance) {
        editorInstance.store.mergeRemoteChanges(() => {
          for (const change of changes) {
            if (change.added) {
              for (const record of Object.values(change.added)) {
                editorInstance.store.put([record])
              }
            }
            if (change.updated) {
              for (const [, to] of Object.values(change.updated)) {
                editorInstance.store.put([to])
              }
            }
            if (change.removed) {
              const ids = Object.keys(change.removed)
              if (ids.length > 0) {
                editorInstance.store.remove(ids)
              }
            }
          }
        })
        store.dispatch('whiteboardApplication/clearRemoteChanges')
      }
    })

    /**
     * Flush accumulated local changes to other clients via the
     * broadcast-changes endpoint. Called on a 100ms throttle.
     */
    const flushBroadcast = async () => {
      if (pendingLocalChanges.length === 0) return

      // Merge all accumulated changes into a single change object.
      const merged = { added: {}, updated: {}, removed: {} }
      for (const change of pendingLocalChanges) {
        if (change.added) {
          Object.assign(merged.added, change.added)
        }
        if (change.updated) {
          for (const [id, val] of Object.entries(change.updated)) {
            merged.updated[id] = val
          }
        }
        if (change.removed) {
          Object.assign(merged.removed, change.removed)
        }
      }
      pendingLocalChanges = []

      try {
        await store.dispatch('whiteboardApplication/broadcastChanges', merged)
      } catch (e) {
        // Silently ignore broadcast errors
      }
    }

    /**
     * Schedule a broadcast flush. Accumulates changes for 100ms
     * before sending.
     */
    const scheduleBroadcast = () => {
      if (broadcastTimer) return
      broadcastTimer = setTimeout(() => {
        broadcastTimer = null
        flushBroadcast()
      }, 100)
    }

    /**
     * Save the full tldraw snapshot to the backend. Only saves when
     * there are unsaved changes (isDirty). Returns a Promise so
     * callers can await the save completing.
     */
    const saveSnapshot = async () => {
      if (!editorInstance || !tldrawModule || !isDirty) return
      try {
        const { document } = tldrawModule.getSnapshot(editorInstance.store)
        await store.dispatch('whiteboardApplication/saveContent', document)
        isDirty = false
      } catch (e) {
        // Silently ignore save errors — will retry on next interval
      }
    }

    /**
     * beforeunload handler — save on tab close / refresh.
     * Uses navigator.sendBeacon as a best-effort fire-and-forget save.
     */
    const onBeforeUnload = () => {
      if (!editorInstance || !tldrawModule || !isDirty) return
      try {
        const { document } = tldrawModule.getSnapshot(editorInstance.store)
        const token = store.getters['auth/token']
        const blob = new Blob([JSON.stringify({ content: document })], {
          type: 'application/json',
        })
        // sendBeacon is fire-and-forget but survives page unload.
        // We can't use PUT with sendBeacon (it only does POST), so
        // we fall back to a synchronous XHR as a last resort.
        const xhr = new XMLHttpRequest()
        xhr.open('PUT', `/api/whiteboard/${props.whiteboardId}/`, false)
        xhr.setRequestHeader('Content-Type', 'application/json')
        xhr.setRequestHeader('Authorization', `JWT ${token}`)
        xhr.send(JSON.stringify({ content: document }))
      } catch (e) {
        // Best effort — nothing we can do if this fails
      }
    }

    onMounted(async () => {
      // Dynamic imports to avoid SSR issues — React and tldraw are
      // client-side only.
      const React = await import('react')
      const { createRoot } = await import('react-dom/client')
      tldrawModule = await import('tldraw')
      await import('tldraw/tldraw.css')

      // After the async imports above, the component may have been
      // unmounted (e.g. rapid navigation between whiteboards). Bail
      // out to avoid the "Target container is not a DOM element" error.
      if (!container.value) return

      const { Tldraw, loadSnapshot } = tldrawModule

      reactRoot = createRoot(container.value)

      const handleMount = (editor) => {
        editorInstance = editor

        // Apply the Baserow user's language to tldraw's UI.
        editor.user.updateUserPreferences({ locale: userLocale.value })

        // Load existing snapshot if provided
        if (
          props.snapshot &&
          typeof props.snapshot === 'object' &&
          Object.keys(props.snapshot).length > 0
        ) {
          try {
            loadSnapshot(editor.store, { document: props.snapshot })
          } catch (e) {
            // If snapshot loading fails, start with a clean canvas
            console.warn('Failed to load whiteboard snapshot:', e)
          }
        }

        // Listen for local user changes and broadcast them
        editor.store.listen(
          (entry) => {
            if (entry.changes) {
              isDirty = true
              pendingLocalChanges.push(entry.changes)
              scheduleBroadcast()
            }
          },
          { source: 'user', scope: 'document' }
        )
      }

      // Asset store that uploads files to Baserow's user-files endpoint
      // instead of embedding them as inline data: URIs. tldraw calls
      // upload() when a user drops or pastes a file, and resolve() when
      // it needs to display an asset.
      const assetStore = {
        async upload(asset, file) {
          const { data } = await UserFileService($client).uploadFile(file)
          return { src: data.url }
        },
        resolve(asset) {
          return asset.props.src
        },
      }

      reactRoot.render(
        React.createElement(Tldraw, {
          onMount: handleMount,
          assets: assetStore,
        })
      )

      // Save every 2 seconds when dirty.
      saveInterval = setInterval(saveSnapshot, 2000)

      // Save on tab close / browser refresh.
      window.addEventListener('beforeunload', onBeforeUnload)

      // Disable Baserow's undo/redo while the whiteboard is active.
      store.dispatch('undoRedo/pushNewScopeSet', {})
    })

    onBeforeUnmount(() => {
      // Restore Baserow's undo/redo scope.
      store.dispatch('undoRedo/popCurrentScopeSet')

      window.removeEventListener('beforeunload', onBeforeUnload)

      if (saveInterval) {
        clearInterval(saveInterval)
        saveInterval = null
      }

      if (broadcastTimer) {
        clearTimeout(broadcastTimer)
        broadcastTimer = null
      }

      if (reactRoot) {
        reactRoot.unmount()
        reactRoot = null
      }

      editorInstance = null
      tldrawModule = null
    })

    return {
      container,
      saveSnapshot,
    }
  },
}
</script>

<style scoped>
.whiteboard__tldraw-container {
  position: absolute;
  inset: 0;
}
</style>

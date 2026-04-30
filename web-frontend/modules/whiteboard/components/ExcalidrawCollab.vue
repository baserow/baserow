<template>
  <client-only>
    <div ref="container" class="whiteboard-canvas" />
  </client-only>
</template>

<script>
import { mapGetters } from 'vuex'
import debounce from 'lodash/debounce'
import { useRuntimeConfig } from '#imports'
import UserFileService from '@baserow/modules/core/services/userFile'

const POINTER_THROTTLE_MS = 50
const BROADCAST_THROTTLE_MS = 100
const AUTOSAVE_DEBOUNCE_MS = 3000
const SCENE_VERSION_NONE = -1

export default {
  name: 'ExcalidrawCollab',
  props: {
    whiteboard: {
      type: Object,
      required: true,
    },
    // VIEWER and COMMENTER roles can read the scene but not modify it.
    // When read-only we hand Excalidraw `viewModeEnabled` so the
    // editing toolbar disappears and every mutating action is blocked,
    // and we skip the autosave / broadcast / image-upload pipeline so
    // the read-only viewer never tries to PUT or POST.
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      controller: null,
      lastBroadcastSceneVersion: SCENE_VERSION_NONE,
      lastSavedSceneVersion: SCENE_VERSION_NONE,
      currentSceneVersion: SCENE_VERSION_NONE,
      uploadedFiles: {},
      latestSnapshot: null,
    }
  },
  computed: {
    ...mapGetters({
      content: 'whiteboardApplication/getContent',
      pendingRemoteUpdates: 'whiteboardApplication/getPendingRemoteUpdates',
      collaborators: 'whiteboardApplication/getCollaborators',
      userLanguage: 'auth/getLanguage',
    }),
    excalidrawLangCode() {
      // Map Baserow's locale codes to the codes Excalidraw ships
      // translations for. Baserow stores the user-selected language on
      // `auth.user.language`; Excalidraw expects a richer locale code
      // (e.g. `nl-NL`). Anything we can't translate falls back to `en`.
      const map = {
        en: 'en',
        de: 'de-DE',
        es: 'es-ES',
        fr: 'fr-FR',
        it: 'it-IT',
        ko: 'ko-KR',
        nl: 'nl-NL',
        pl: 'pl-PL',
        uk: 'uk-UA',
      }
      return map[this.userLanguage] || 'en'
    },
  },
  watch: {
    pendingRemoteUpdates: {
      handler(updates) {
        if (!updates || updates.length === 0 || !this.controller) return
        for (const update of updates) {
          if (update.kind === 'scene') {
            this.controller.applyRemoteScene(update.elements || [])
            if (update.files && Object.keys(update.files).length > 0) {
              this.controller.applyRemoteFiles(update.files)
            }
          }
        }
        this.$store.dispatch('whiteboardApplication/clearRemoteUpdates')
      },
    },
    collaborators: {
      handler(value) {
        if (!this.controller) return
        this.controller.setCollaborators(value || {})
      },
      deep: true,
    },
    excalidrawLangCode(newCode) {
      // The user changed their Baserow language while the whiteboard
      // is open — push the new locale into Excalidraw without
      // remounting so the scene state is preserved.
      if (this.controller) {
        this.controller.setLangCode(newCode)
      }
    },
  },
  async mounted() {
    if (!import.meta.client) return
    const { mountExcalidraw } = await import('./excalidrawReactRoot.js')

    const initialContent = this.content || {}
    // Pre-load already-uploaded files (server URLs) into the override
    // map so we never re-upload them.
    this.uploadedFiles = Object.fromEntries(
      Object.values(initialContent.files || {})
        .filter((f) => f && f.id && f.dataURL && !this._isDataUrl(f.dataURL))
        .map((f) => [f.id, f])
    )

    this.controller = mountExcalidraw(this.$refs.container, {
      initialData: {
        elements: initialContent.elements || [],
        appState: {
          ...(initialContent.appState || {}),
          collaborators: new Map(),
        },
        files: initialContent.files || {},
      },
      viewModeEnabled: this.readOnly,
      langCode: this.excalidrawLangCode,
      // Read-only viewers don't broadcast or autosave; the editing
      // pipelines are wired to no-ops so onChange / onPointerUpdate
      // events from Excalidraw (which still fire for hover/selection)
      // can't sneak a PUT or POST through.
      onChange: this.readOnly ? () => {} : this._handleSceneChange,
      onPointerUpdate: this.readOnly ? () => {} : this._handlePointerUpdate,
    })

    // Excalidraw ships its own undo/redo for Cmd/Ctrl+Z and
    // Cmd/Ctrl+Shift+Z. Baserow's global handler in `core/layouts/app.vue`
    // listens on `document.body` (bubble phase) and would also fire,
    // undoing an unrelated workspace action. The keydown event bubbles
    // through this container on its way to body, so stopping propagation
    // here keeps the keystroke contained to Excalidraw without touching
    // any core code. Excalidraw's listener runs earlier in the bubble
    // path (or in capture), so it still receives the event.
    this.$refs.container.addEventListener(
      'keydown',
      this._stopUndoRedoPropagation
    )
    if (!this.readOnly) {
      window.addEventListener('beforeunload', this._flushOnUnload)
    }
  },
  beforeUnmount() {
    if (this.$refs.container) {
      this.$refs.container.removeEventListener(
        'keydown',
        this._stopUndoRedoPropagation
      )
    }
    if (this.controller) {
      this.controller.unmount()
      this.controller = null
    }
    if (!this.readOnly && this._debouncedAutosave?.flush) {
      this._debouncedAutosave.flush()
    }
    if (!this.readOnly) {
      window.removeEventListener('beforeunload', this._flushOnUnload)
    }
  },
  created() {
    this._debouncedAutosave = debounce(
      this._persistSnapshot,
      AUTOSAVE_DEBOUNCE_MS
    )
    this._broadcastScene = this._throttle(
      this._broadcastSceneNow,
      BROADCAST_THROTTLE_MS
    )
    this._broadcastPointer = this._throttle(
      this._broadcastPointerNow,
      POINTER_THROTTLE_MS
    )
  },
  methods: {
    _isDataUrl(value) {
      return typeof value === 'string' && value.startsWith('data:')
    },
    _stopUndoRedoPropagation(event) {
      const isMod = event.metaKey || event.ctrlKey
      if (isMod && event.key.toLowerCase() === 'z') {
        event.stopPropagation()
      }
    },
    _throttle(fn, delay) {
      let lastCall = 0
      let timer = null
      let pendingArgs = null
      const invoke = () => {
        lastCall = Date.now()
        timer = null
        const args = pendingArgs
        pendingArgs = null
        fn(...(args || []))
      }
      return (...args) => {
        const now = Date.now()
        const remaining = delay - (now - lastCall)
        pendingArgs = args
        if (remaining <= 0) {
          if (timer) {
            clearTimeout(timer)
            timer = null
          }
          invoke()
        } else if (!timer) {
          timer = setTimeout(invoke, remaining)
        }
      }
    },
    async _handleSceneChange({ elements, appState, files, sceneVersion }) {
      // Replace any base64 dataURL entries with the user_files URL we
      // already uploaded. Without this overlay, every onChange would
      // reset latestSnapshot.files back to whatever Excalidraw is
      // holding in memory (base64) and the next autosave would PUT
      // base64 even though we already have a URL on the server.
      this.latestSnapshot = {
        elements,
        appState: this._serializableAppState(appState),
        files: this._overlayUploadedFiles(files || {}),
      }

      await this._uploadNewFiles(files || {})

      // Excalidraw's onChange fires on every interaction (selection,
      // hover, scroll, even just clicking on the canvas). The scene
      // version only advances when the actual scene content changes, so
      // skip the WS broadcast and autosave when nothing changed.
      if (sceneVersion === this.currentSceneVersion) return
      this.currentSceneVersion = sceneVersion

      this._broadcastScene()
      this._debouncedAutosave()
    },
    _overlayUploadedFiles(files) {
      const out = {}
      for (const [id, file] of Object.entries(files)) {
        out[id] = this.uploadedFiles[id] || file
      }
      return out
    },
    _serializableAppState(appState) {
      // Avoid persisting the live collaborators Map; reset it on read.
      const { collaborators, ...rest } = appState || {}
      return rest
    },
    async _broadcastSceneNow() {
      if (!this.controller || !this.latestSnapshot) return
      if (this.currentSceneVersion === this.lastBroadcastSceneVersion) return
      this.lastBroadcastSceneVersion = this.currentSceneVersion

      const payload = {
        type: 'scene_update',
        whiteboard_id: this.whiteboard.id,
        elements: this.latestSnapshot.elements,
        files: this.latestSnapshot.files,
      }
      this.$store.dispatch('whiteboardApplication/broadcastChanges', payload)
    },
    _broadcastPointerNow(payload) {
      if (!this.whiteboard) return
      const user = this.$store.getters['auth/getUserObject']
      this.$store.dispatch('whiteboardApplication/broadcastChanges', {
        type: 'pointer_update',
        whiteboard_id: this.whiteboard.id,
        user_id: user?.id,
        username: user?.first_name || user?.username || '',
        color: this._userColor(user?.id),
        pointer: payload.pointer,
        button: payload.button,
      })
    },
    _userColor(userId) {
      if (userId == null) return '#888'
      const palette = [
        '#5B8FF9',
        '#5AD8A6',
        '#F6BD16',
        '#E86452',
        '#6DC8EC',
        '#945FB9',
        '#FF9845',
        '#1E9493',
      ]
      return palette[Math.abs(Number(userId)) % palette.length]
    },
    _handlePointerUpdate(payload) {
      this._broadcastPointer(payload)
    },
    async _uploadNewFiles(files) {
      if (!this.$client) return
      const newEntries = Object.values(files).filter((file) => {
        if (!file || !file.id || !file.dataURL) return false
        if (this.uploadedFiles[file.id]) return false
        return this._isDataUrl(file.dataURL)
      })

      for (const file of newEntries) {
        try {
          const blob = await this._dataUrlToBlob(file.dataURL)
          const ext = (file.mimeType || blob.type || '').split('/')[1] || 'bin'
          const filename = `whiteboard-${file.id}.${ext}`
          const { data } = await UserFileService(this.$client).uploadFile(
            new File([blob], filename, { type: blob.type })
          )
          const uploaded = {
            id: file.id,
            dataURL: data.url,
            mimeType: file.mimeType,
            created: file.created || Date.now(),
          }
          this.uploadedFiles[file.id] = uploaded
          if (this.latestSnapshot?.files) {
            this.latestSnapshot.files[file.id] = uploaded
          }
        } catch (e) {
          console.warn('whiteboard: failed to upload image', e)
        }
      }
    },
    async _dataUrlToBlob(dataURL) {
      const response = await fetch(dataURL)
      return await response.blob()
    },
    async _persistSnapshot() {
      if (!this.latestSnapshot) return
      if (this.currentSceneVersion === this.lastSavedSceneVersion) return
      this.lastSavedSceneVersion = this.currentSceneVersion

      try {
        await this.$store.dispatch(
          'whiteboardApplication/saveContent',
          this.latestSnapshot
        )
      } catch (e) {
        console.warn('whiteboard: failed to persist snapshot', e)
      }
    },
    _flushOnUnload() {
      if (!this.latestSnapshot || !import.meta.client) return
      try {
        const config = useRuntimeConfig()
        const url = `${config.public.publicBackendUrl}/api/whiteboard/${this.whiteboard.id}/`
        const token = this.$store.getters['auth/token']
        const blob = new Blob(
          [JSON.stringify({ content: this.latestSnapshot })],
          { type: 'application/json' }
        )
        if (token) {
          const headers = new Headers({ 'Content-Type': 'application/json' })
          headers.set('Authorization', `JWT ${token}`)
          // sendBeacon doesn't allow custom headers; fall back to keepalive fetch.
          fetch(url, {
            method: 'PUT',
            body: blob,
            headers,
            keepalive: true,
          }).catch(() => {})
        } else {
          navigator.sendBeacon?.(url, blob)
        }
      } catch {
        /* noop */
      }
    },
  },
}
</script>

<style lang="scss">
.whiteboard-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: flex;
}
</style>

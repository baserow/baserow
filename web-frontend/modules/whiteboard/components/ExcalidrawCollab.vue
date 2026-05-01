<template>
  <client-only>
    <div
      ref="wrapper"
      class="whiteboard-canvas"
      :class="{ 'whiteboard-canvas--comment-mode': commentModeActive }"
    >
      <!--
        React mounts Excalidraw INTO `container` and React's reconciler
        manages every child of that node. We must NOT let Vue render
        siblings inside `container`, or React will tear them down on
        first render. Keep `container` empty and put Vue overlays as
        siblings inside the wrapper instead.
      -->
      <div ref="container" class="whiteboard-canvas__excalidraw" />
      <WhiteboardCommentLayer
        v-if="canViewComments"
        :whiteboard="whiteboard"
        :read-only="!canComment"
        :app-state="excalidrawAppState"
        :viewport-converter="_viewportConverter"
        @cancel-draft="_onCancelDraft"
      />
    </div>
  </client-only>
</template>

<script>
import { mapGetters } from 'vuex'
import debounce from 'lodash/debounce'
import { useRuntimeConfig } from '#imports'
import UserFileService from '@baserow/modules/core/services/userFile'
import WhiteboardCommentLayer from '@baserow/modules/whiteboard/components/comments/WhiteboardCommentLayer.vue'

const POINTER_THROTTLE_MS = 50
const BROADCAST_THROTTLE_MS = 100
const AUTOSAVE_DEBOUNCE_MS = 3000
const SCENE_VERSION_NONE = -1

export default {
  name: 'ExcalidrawCollab',
  components: { WhiteboardCommentLayer },
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
    // VIEWER role can read but not post comments. EDITOR/BUILDER/ADMIN
    // get the full canCreate flag. We piggy-back on the whiteboard
    // permission registry; the page checks `whiteboard.create_comment`
    // and passes it down here.
    canComment: {
      type: Boolean,
      required: false,
      default: true,
    },
    // COMMENTER and above can list / see comments. VIEWERs cannot —
    // when this is false the comment overlay is not rendered at all
    // and the toolbar Comment button is hidden via `canComment`.
    canViewComments: {
      type: Boolean,
      required: false,
      default: true,
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
      // Latest appState snapshot from Excalidraw — fed into the comment
      // overlay so pin positions track pan/zoom in real time.
      excalidrawAppState: {
        scrollX: 0,
        scrollY: 0,
        zoom: 1,
        offsetLeft: 0,
        offsetTop: 0,
        width: 0,
        height: 0,
      },
    }
  },
  computed: {
    ...mapGetters({
      content: 'whiteboardApplication/getContent',
      pendingRemoteUpdates: 'whiteboardApplication/getPendingRemoteUpdates',
      collaborators: 'whiteboardApplication/getCollaborators',
      userLanguage: 'auth/getLanguage',
      commentModeActive: 'whiteboardComments/isCommentModeActive',
      openThreadId: 'whiteboardComments/getOpenThreadId',
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
            const appliedVersion = this.controller.applyRemoteScene(
              update.elements || []
            )
            // Stamp the new version BEFORE Excalidraw's onChange fires.
            // The handler short-circuits when sceneVersion ===
            // currentSceneVersion, so a remote-applied scene won't
            // round-trip back as a broadcast + autosave, breaking the
            // ping-pong loop between connected clients.
            if (appliedVersion != null) {
              this.currentSceneVersion = appliedVersion
              this.lastBroadcastSceneVersion = appliedVersion
              this.lastSavedSceneVersion = appliedVersion
            }
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
    commentModeActive(active) {
      // Sync the React-side button highlight when the store flips the
      // flag (e.g. after the user closes the draft popup).
      if (this.controller) {
        this.controller.setCommentModeActive(active)
      }
      this._syncCommentClickListener(active)
      this._syncEscapeListener()
    },
    openThreadId(id) {
      // While a popup is open, install a global capture listener that
      // closes it when the user clicks outside. Removed as soon as the
      // popup goes away.
      this._syncOutsideClickListener(id != null)
      this._syncEscapeListener()
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
      canComment: this.canComment,
      initialCommentModeActive: this.commentModeActive,
      commentButtonLabel: this.$t('whiteboardComments.toolbarComment'),
      onCommentButtonClick: (active) => {
        this.$store.dispatch('whiteboardComments/setCommentModeActive', active)
      },
      onAppStateChange: (appState) => {
        this.excalidrawAppState = appState
      },
      // Read-only viewers don't broadcast or autosave; the editing
      // pipelines are wired to no-ops so onChange / onPointerUpdate
      // events from Excalidraw (which still fire for hover/selection)
      // can't sneak a PUT or POST through.
      onChange: this.readOnly ? () => {} : this._handleSceneChange,
      onPointerUpdate: this.readOnly ? () => {} : this._handlePointerUpdate,
    })

    // Initial app-state snapshot, in case Excalidraw's first render
    // happens before any user interaction.
    const initialAppState = this.controller.getAppState?.()
    if (initialAppState) {
      this.excalidrawAppState = {
        scrollX: initialAppState.scrollX,
        scrollY: initialAppState.scrollY,
        zoom: initialAppState.zoom?.value ?? initialAppState.zoom ?? 1,
        offsetLeft: initialAppState.offsetLeft,
        offsetTop: initialAppState.offsetTop,
        width: initialAppState.width,
        height: initialAppState.height,
      }
    }

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

    // If the store boots with comment mode already active (e.g. user
    // navigated away and back while a popup was open), wire up the
    // capture listener immediately.
    this._syncCommentClickListener(this.commentModeActive)
  },
  beforeUnmount() {
    if (this.$refs.container) {
      this.$refs.container.removeEventListener(
        'keydown',
        this._stopUndoRedoPropagation
      )
    }
    this._syncCommentClickListener(false)
    this._syncOutsideClickListener(false)
    if (this._escapeListener) {
      document.removeEventListener('keydown', this._escapeListener, true)
      this._escapeListener = null
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
    _viewportConverter(sceneX, sceneY) {
      // Project a scene coordinate to a position relative to the
      // overlay layer (NOT the page).
      //
      // Excalidraw's own `sceneCoordsToViewportCoords` adds
      // `offsetLeft/offsetTop`, which are the canvas's offsets from the
      // page (driven by the layout's left sidebar etc.). Our overlay is
      // already absolutely positioned at `inset: 0` of the same wrapper
      // Excalidraw renders into, so it inherits those offsets — adding
      // them again would double-count and the pin drifts horizontally
      // every time the user zooms (vertically there's no top offset so
      // it looked correct). Use the projection without the offsets.
      const s = this.excalidrawAppState
      return {
        x: (sceneX + s.scrollX) * s.zoom,
        y: (sceneY + s.scrollY) * s.zoom,
      }
    },
    _onCancelDraft() {
      this.$store.dispatch('whiteboardComments/cancelDraftPin')
    },
    _syncEscapeListener() {
      // Install a single document-level keydown listener whenever we
      // need to react to Escape — i.e., the comment toggle is on or a
      // popup is open. Removed as soon as both are off so it doesn't
      // intercept Escape elsewhere in Baserow.
      const shouldListen = this.commentModeActive || this.openThreadId != null
      if (shouldListen && !this._escapeListener) {
        this._escapeListener = (event) => {
          if (event.key !== 'Escape') return
          // Popup takes precedence: close it (and discard any draft).
          if (this.openThreadId != null) {
            event.preventDefault()
            this.$store.dispatch('whiteboardComments/cancelDraftPin')
            this.$store.dispatch('whiteboardComments/closeThread')
            return
          }
          // Otherwise untoggle comment mode.
          if (this.commentModeActive) {
            event.preventDefault()
            this.$store.dispatch(
              'whiteboardComments/setCommentModeActive',
              false
            )
          }
        }
        document.addEventListener('keydown', this._escapeListener, true)
      } else if (!shouldListen && this._escapeListener) {
        document.removeEventListener('keydown', this._escapeListener, true)
        this._escapeListener = null
      }
    },
    _syncOutsideClickListener(shouldListen) {
      if (shouldListen && !this._outsideClickListener) {
        this._outsideClickListener = (event) => {
          // The popup itself stops `click` propagation, so any click
          // that reaches this document-level listener happened OUTSIDE
          // the popup. Pin clicks would also reach here, but pins emit
          // their own `open` action which switches the popup — guard
          // against closing in that case.
          if (event.target.closest?.('.whiteboard-comment-thread')) return
          if (event.target.closest?.('.whiteboard-comment-pin')) return
          // Cancel any pending draft and close the popup.
          this.$store.dispatch('whiteboardComments/cancelDraftPin')
          this.$store.dispatch('whiteboardComments/closeThread')
        }
        // Use the bubble phase so the popup's own `@click.stop` (and
        // pin's `@click.stop`) get a chance to halt propagation before
        // we run our outside-click logic.
        document.addEventListener(
          'pointerdown',
          this._outsideClickListener,
          false
        )
      } else if (!shouldListen && this._outsideClickListener) {
        document.removeEventListener(
          'pointerdown',
          this._outsideClickListener,
          false
        )
        this._outsideClickListener = null
      }
    },
    _syncCommentClickListener(shouldListen) {
      const el = this.$refs.container
      if (!el) return
      if (shouldListen && !this._commentClickListener) {
        this._commentClickListener = (event) => {
          // Ignore clicks that originate from our own UI — the comment
          // button, popups, the layer's own pins, or the resolved-toggle.
          if (event.target.closest('.whiteboard-top-right-button')) return
          if (event.target.closest('.whiteboard-comment-overlay')) return
          if (!this.controller) return
          const scene = this.controller.viewportToScene(
            event.clientX,
            event.clientY
          )
          if (!scene) return
          // Stop Excalidraw from also processing the click — otherwise
          // the user would draw a shape under the new pin.
          event.preventDefault()
          event.stopPropagation()
          this.$store.dispatch('whiteboardComments/openDraftPin', {
            x: scene.x,
            y: scene.y,
          })
        }
        el.addEventListener('pointerdown', this._commentClickListener, true)
        // Capture phase so we run before Excalidraw's own listener.
      } else if (!shouldListen && this._commentClickListener) {
        el.removeEventListener('pointerdown', this._commentClickListener, true)
        this._commentClickListener = null
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
// Custom buttons rendered by `excalidrawReactRoot.js` via Excalidraw's
// `renderTopRightUI` prop. Excalidraw's `.layer-ui__wrapper__top-right`
// sets `pointer-events: none !important` so the click-through canvas
// keeps working; children must opt back in. Without this, clicking the
// Comment button does nothing because the click never reaches it.
// Custom button rendered by `excalidrawReactRoot.js` via Excalidraw's
// `renderTopRightUI` prop. Excalidraw's `.layer-ui__wrapper__top-right`
// sets `pointer-events: none !important` so the click-through canvas
// keeps working; children must opt back in. We also size the button
// using Excalidraw's own CSS variables so the comment toggle matches
// the height of the neighbouring Library button (and its icon scales
// with `--lg-icon-size`).
.whiteboard-top-right-buttons {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  pointer-events: auto;
}
.whiteboard-top-right-button {
  pointer-events: auto;
  background-color: var(--color-surface-low, #f5f5f5);
  color: var(--text-primary-color, #1e1e1e);
  border: none;
  box-shadow: 0 0 0 1px var(--color-surface-lowest, #ffffff);
  border-radius: var(--border-radius-lg, 8px);
  width: var(--lg-button-size, 2.5rem);
  height: var(--lg-button-size, 2.5rem);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  line-height: 0;
  font-family: var(--ui-font, inherit);
  svg {
    width: var(--lg-icon-size, 1.25rem);
    height: var(--lg-icon-size, 1.25rem);
  }
  // Match the hover styling of the neighbouring Library trigger
  // (`.sidebar-trigger:hover`) so the two buttons feel like one
  // toolbar.
  &:hover {
    background-color: var(--button-hover-bg, var(--island-bg-color, #ffffff));
    color: var(
      --button-hover-color,
      var(--button-color, var(--text-primary-color, inherit))
    );
  }
  &--active {
    background-color: var(--color-surface-primary-container, #5b8ff9);
    color: var(--color-on-primary-container, #ffffff);
    &:hover {
      background-color: var(--color-surface-primary-container, #5b8ff9);
      color: var(--color-on-primary-container, #ffffff);
    }
  }
}

.whiteboard-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: flex;
}
.whiteboard-canvas__excalidraw {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
// Crosshair cursor while comment mode is active so it's obvious that
// the next click on the canvas drops a pin. Excalidraw assigns its own
// cursor inline on the canvas via JS based on the active tool, so we
// need a universal selector with `!important` to win the cascade.
// `:deep()` is only valid inside `<style scoped>` and this block isn't
// scoped, so we don't use it.
.whiteboard-canvas--comment-mode,
.whiteboard-canvas--comment-mode * {
  cursor: crosshair !important;
}
</style>

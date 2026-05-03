import React, { useCallback, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Excalidraw,
  reconcileElements,
  CaptureUpdateAction,
  getSceneVersion,
  sceneCoordsToViewportCoords,
  useHandleLibrary,
  viewportCoordsToSceneCoords,
} from '@excalidraw/excalidraw'

import excalidrawCss from '@excalidraw/excalidraw/index.css?raw'

// Excalidraw's stylesheet is written assuming the browser default
// `html { font-size: 16px }` — so its `2rem` toolbar buttons render at
// 32px on excalidraw.com. Baserow sets `html { font-size: 62.5% }` in
// `web-frontend/modules/core/assets/scss/typography.scss` to make
// `1rem = 10px` for the rest of the app, which silently shrinks every
// Excalidraw control to 62.5% of its intended size.
//
// We load Excalidraw's stylesheet as raw text, rewrite it, and inject
// the result into <head>. We deliberately skip the normal
// `import '...index.css'`: that would load a second, rem-based copy
// and the cascade between them is unpredictable.
//
// Three transforms run on the raw CSS:
//
//  1. Every `Xrem` is rewritten to `(X*16)px`. Excalidraw's CSS
//     assumes the browser default `html { font-size: 16px }`, but
//     Baserow sets `html { font-size: 62.5% }` in
//     `web-frontend/modules/core/assets/scss/typography.scss` to make
//     `1rem = 10px` for the rest of the app, which silently shrinks
//     every Excalidraw control to 62.5% of its intended size.
//     Converting to absolute pixels side-steps the html font-size
//     entirely.
//
//  2. The four `@font-face` blocks for the bundled "Assistant" family
//     are stripped. Their `url()` paths (`./fonts/Assistant/*.woff2`)
//     resolve against the page when injected as raw text and 404 in
//     dev. The font subpaths are not exposed through the package's
//     `exports` field, so re-pointing them to bundled assets is
//     awkward.
//
//  3. References to the "Assistant" family are remapped to "Inter",
//     which Baserow already loads in
//     `web-frontend/modules/core/assets/scss/variables.scss`. This
//     matches the rest of the app's typography and avoids any
//     downloadable-font failures.
//
// The remaining `url()` calls in the bundle are inline `data:` URIs
// (one sortable handle, four SVG arrows) and survive untouched.
;(function injectExcalidrawCss() {
  if (typeof document === 'undefined') return
  const id = 'baserow-excalidraw-css'
  if (document.getElementById(id)) return

  const fixed = excalidrawCss
    .replace(/(-?\d*\.?\d+)rem\b/g, (_, n) => `${parseFloat(n) * 16}px`)
    .replace(/@font-face\s*\{[^}]*\}/g, '')
    .replace(/\bAssistant\b/g, 'Inter')

  const styleEl = document.createElement('style')
  styleEl.id = id
  styleEl.textContent = fixed
  document.head.appendChild(styleEl)
})()

/**
 * Renders the Excalidraw React component inside the supplied DOM container
 * and bridges its imperative API back to the host (Vue) layer.
 *
 * This file is intentionally written without JSX syntax. Nuxt always loads
 * `@vitejs/plugin-vue-jsx`, which transforms `<X />` in any .jsx/.tsx file
 * to Vue's `h()` and so produces Vue VNodes that React cannot render.
 * Calling `React.createElement` directly bypasses every JSX plugin so this
 * module compiles cleanly to React elements no matter what plugin order
 * Vite ends up with.
 *
 * Returned controller exposes the methods the Vue host needs:
 *   - getApi()                 -> the ExcalidrawImperativeAPI (or null)
 *   - applyRemoteScene(elems)  -> merges remote elements via reconcileElements
 *   - applyRemoteFiles(files)  -> registers binary files (images)
 *   - setCollaborators(map)    -> updates the Map<string, Collaborator>
 *   - unmount()                -> tears down the React root
 */
export function mountExcalidraw(container, options) {
  const {
    initialData,
    onChange,
    onPointerUpdate,
    viewModeEnabled = false,
    langCode: initialLangCode = 'en',
    onCommentButtonClick,
    commentButtonLabel = 'Comment',
    canComment = true,
    initialCommentModeActive = false,
    onAppStateChange,
    onUserFollow,
  } = options

  const apiRef = { current: null }
  const e = React.createElement

  // Captured setState handles so the Vue host can flip these flags at
  // runtime via the returned controller without remounting Excalidraw.
  let setLangCodeFn = null
  let setCommentModeActiveFn = null

  const ExcalidrawHost = () => {
    const localApiRef = useRef(null)
    const [api, setApi] = useState(null)
    const [langCode, setLangCode] = useState(initialLangCode)
    const [commentModeActive, setCommentModeActive] = useState(
      initialCommentModeActive
    )
    setLangCodeFn = setLangCode
    setCommentModeActiveFn = setCommentModeActive

    // Wire Excalidraw's `#addLibrary=…` install flow. Excalidraw
    // exposes this as a hook that:
    //  - reads the URL hash on mount,
    //  - subscribes to `hashchange`,
    //  - validates the source URL (default validator allows
    //    `*.excalidraw.com`, which covers `libraries.excalidraw.com`),
    //  - fetches the `.excalidrawlib` payload, and
    //  - calls `api.updateLibrary(...)` for us.
    // Without this, navigating to `…#addLibrary=<url>` does nothing —
    // hence the user-reported bug where clicking "Add to Excalidraw"
    // on libraries.excalidraw.com landed on the page but never added
    // anything.
    useHandleLibrary({ excalidrawAPI: api })

    const handleApiReady = useCallback((readyApi) => {
      localApiRef.current = readyApi
      apiRef.current = readyApi
      // Promote to state so `useHandleLibrary` re-runs once the API is
      // available (it accepts `null` initially and re-wires when the
      // value becomes non-null).
      setApi(readyApi)
      // Subscribe to user-follow events through the imperative API.
      // Passing `onUserFollow` as a prop is silently a no-op in
      // current `@excalidraw/excalidraw` — the runtime only exposes
      // the emitter via `api.onUserFollow(cb)`, and the prop in the
      // type definitions is never wired up. Same is true for
      // `onScrollChange`, `onPointerDown`, `onPointerUp`. Discovered
      // by grepping the bundle: there are only three references to
      // `onUserFollowEmitter` — the constructor, the imperative
      // exposure, and the trigger sites. Nothing reads
      // `props.onUserFollow`.
      if (
        typeof onUserFollow === 'function' &&
        typeof readyApi.onUserFollow === 'function'
      ) {
        readyApi.onUserFollow(onUserFollow)
      }
    }, [])

    // Custom button rendered into Excalidraw's top-right area, the only
    // officially-supported toolbar extension hook. We size it to match
    // the neighbouring Library trigger (`--lg-button-size`) so the row
    // stays uniform, and use an inline SVG so we don't depend on a
    // Vue-side icon registry from inside the React tree.
    const renderTopRightUI = () => {
      if (!canComment) return null
      return e(
        'div',
        { className: 'whiteboard-top-right-buttons' },
        e(
          'button',
          {
            key: 'whiteboard-comment-toggle',
            type: 'button',
            title: commentButtonLabel,
            'aria-label': commentButtonLabel,
            'aria-pressed': commentModeActive ? 'true' : 'false',
            className:
              'whiteboard-top-right-button' +
              (commentModeActive ? ' whiteboard-top-right-button--active' : ''),
            onClick: () => {
              const next = !commentModeActive
              setCommentModeActive(next)
              if (typeof onCommentButtonClick === 'function') {
                onCommentButtonClick(next)
              }
            },
          },
          e(
            'svg',
            {
              viewBox: '0 0 24 24',
              fill: 'none',
              stroke: 'currentColor',
              strokeWidth: '2',
              strokeLinecap: 'round',
              strokeLinejoin: 'round',
              'aria-hidden': 'true',
              focusable: 'false',
            },
            e('path', {
              d: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z',
            })
          )
        )
      )
    }

    return e(
      'div',
      { style: { width: '100%', height: '100%' } },
      e(Excalidraw, {
        excalidrawAPI: handleApiReady,
        initialData,
        viewModeEnabled,
        langCode,
        renderTopRightUI,
        onChange: (elements, appState, files) => {
          if (typeof onAppStateChange === 'function') {
            // Cheap callback for the comment overlay — fires on every
            // pan/zoom/element change so pin positions can re-project.
            onAppStateChange({
              scrollX: appState.scrollX,
              scrollY: appState.scrollY,
              zoom: appState.zoom?.value ?? appState.zoom,
              width: appState.width,
              height: appState.height,
              offsetLeft: appState.offsetLeft,
              offsetTop: appState.offsetTop,
            })
          }
          if (typeof onChange === 'function') {
            onChange({
              elements,
              appState,
              files,
              sceneVersion: getSceneVersion(elements),
            })
          }
        },
        onPointerUpdate: (payload) => {
          if (typeof onPointerUpdate === 'function') {
            onPointerUpdate(payload)
          }
        },
        // NOTE: we intentionally don't pass `onUserFollow` here.
        // Excalidraw doesn't honor the prop — subscription happens
        // through the imperative API in `handleApiReady` above.
      })
    )
  }

  const root = createRoot(container)
  root.render(e(ExcalidrawHost))

  return {
    getApi() {
      return apiRef.current
    },
    applyRemoteScene(remoteElements) {
      const api = apiRef.current
      if (!api) return null
      const localElements = api.getSceneElementsIncludingDeleted()
      const localAppState = api.getAppState()
      const reconciled = reconcileElements(
        localElements,
        remoteElements,
        localAppState
      )
      api.updateScene({
        elements: reconciled,
        captureUpdate: CaptureUpdateAction.NEVER,
      })
      // Return the sceneVersion of the just-applied scene so the Vue
      // host can stamp `currentSceneVersion` BEFORE Excalidraw fires
      // `onChange`. Without this, the host sees the remote-driven
      // version as a new local edit and broadcasts/autosaves it back,
      // creating a 3-second ping-pong between every connected client.
      return getSceneVersion(reconciled)
    },
    /** Move the local viewport to match a remote user's viewport. Used
     *  by the "follow user" feature — every `viewport_update` from the
     *  followed user is funnelled through here.
     *
     *  The remote payload carries the followed user's `(scrollX,
     *  scrollY, zoom, width, height)`. If we just copied scrollX /
     *  scrollY / zoom 1:1, two browsers with different canvas sizes
     *  would diverge: the same scroll/zoom values describe a different
     *  visible scene rect on a smaller canvas, and the follower would
     *  see less (or differently-anchored) content.
     *
     *  Excalidraw's projection is `viewportX = (sceneX + scrollX) *
     *  zoom`. Inverting at the screen edges gives the remote's visible
     *  scene rect:
     *    sceneLeft   = -scrollX
     *    sceneRight  = -scrollX + remoteWidth  / remoteZoom
     *    sceneTop    = -scrollY
     *    sceneBottom = -scrollY + remoteHeight / remoteZoom
     *
     *  We pick a local zoom that fits that rect inside our canvas,
     *  then anchor the local viewport so its scene-center matches the
     *  remote's scene-center. Result: the follower's screen shows the
     *  same content the followed user is looking at, regardless of
     *  window size. */
    applyRemoteViewport({ scrollX, scrollY, zoom, width, height }) {
      const api = apiRef.current
      if (!api) return
      if (
        typeof scrollX !== 'number' ||
        typeof scrollY !== 'number' ||
        typeof zoom !== 'number'
      ) {
        return
      }
      const local = api.getAppState()
      const localW = local.width || 0
      const localH = local.height || 0
      const remoteW = typeof width === 'number' && width > 0 ? width : localW
      const remoteH = typeof height === 'number' && height > 0 ? height : localH
      if (remoteW === 0 || remoteH === 0 || localW === 0 || localH === 0) {
        // Nothing useful we can do without dimensions on either side —
        // fall back to copying the raw values so a reasonable default
        // still lands.
        api.updateScene({
          appState: { scrollX, scrollY, zoom: { value: zoom } },
          captureUpdate: CaptureUpdateAction.NEVER,
        })
        return
      }
      // Remote visible scene rect in scene coords.
      const remoteSceneW = remoteW / zoom
      const remoteSceneH = remoteH / zoom
      const remoteCenterX = -scrollX + remoteSceneW / 2
      const remoteCenterY = -scrollY + remoteSceneH / 2
      // Pick the largest zoom that fits the remote rect into the local
      // canvas so nothing the followed user is seeing overflows our
      // viewport. Letterboxing on whichever axis has slack.
      const fitZoom = Math.min(localW / remoteSceneW, localH / remoteSceneH)
      const nextScrollX = localW / 2 / fitZoom - remoteCenterX
      const nextScrollY = localH / 2 / fitZoom - remoteCenterY
      api.updateScene({
        appState: {
          scrollX: nextScrollX,
          scrollY: nextScrollY,
          zoom: { value: fitZoom },
        },
        captureUpdate: CaptureUpdateAction.NEVER,
      })
    },
    applyRemoteFiles(files) {
      const api = apiRef.current
      if (!api || !files) return
      const list = Array.isArray(files)
        ? files
        : Object.values(files).filter(Boolean)
      if (list.length === 0) return
      api.addFiles(list)
    },
    setLangCode(code) {
      if (typeof setLangCodeFn === 'function') {
        setLangCodeFn(code || 'en')
      }
    },
    setCommentModeActive(active) {
      if (typeof setCommentModeActiveFn === 'function') {
        setCommentModeActiveFn(!!active)
      }
    },
    /** Returns the current appState — useful to convert a click's
     *  viewport coords to scene coords on demand. */
    getAppState() {
      const api = apiRef.current
      if (!api) return null
      return api.getAppState()
    },
    /** Convert a page-relative pointer position to scene coordinates
     *  using Excalidraw's own helper, so pin placement matches the
     *  exact pixel the user clicked on regardless of zoom or pan. */
    viewportToScene(clientX, clientY) {
      const api = apiRef.current
      if (!api) return null
      const appState = api.getAppState()
      return viewportCoordsToSceneCoords(
        { clientX, clientY },
        {
          zoom: appState.zoom,
          offsetLeft: appState.offsetLeft,
          offsetTop: appState.offsetTop,
          scrollX: appState.scrollX,
          scrollY: appState.scrollY,
        }
      )
    },
    /** Convert scene coordinates to page-relative pixels for rendering
     *  HTML pins on top of the canvas. */
    sceneToViewport(sceneX, sceneY) {
      const api = apiRef.current
      if (!api) return null
      const appState = api.getAppState()
      return sceneCoordsToViewportCoords(
        { sceneX, sceneY },
        {
          zoom: appState.zoom,
          offsetLeft: appState.offsetLeft,
          offsetTop: appState.offsetTop,
          scrollX: appState.scrollX,
          scrollY: appState.scrollY,
        }
      )
    },
    setCollaborators(collaboratorsObject) {
      const api = apiRef.current
      if (!api) return
      const map = new Map()
      for (const [id, value] of Object.entries(collaboratorsObject || {})) {
        const socketId = String(id)
        // Excalidraw's `onUserFollow` reports back the collaborator's
        // `socketId` field (NOT the map key). Without it the payload
        // arrives as `{ userToFollow: { socketId: undefined } }` and
        // we have no way to identify which user was clicked. We use
        // the same string-coerced auth id as the map key.
        map.set(socketId, { ...value, socketId })
      }
      api.updateScene({
        collaborators: map,
        captureUpdate: CaptureUpdateAction.NEVER,
      })
    },
    unmount() {
      try {
        root.unmount()
      } catch {
        /* noop */
      }
      apiRef.current = null
    },
  }
}

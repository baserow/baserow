import React, { useCallback, useRef } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Excalidraw,
  reconcileElements,
  CaptureUpdateAction,
  getSceneVersion,
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
  } = options

  const apiRef = { current: null }
  const e = React.createElement

  const ExcalidrawHost = () => {
    const localApiRef = useRef(null)

    const handleApiReady = useCallback((api) => {
      localApiRef.current = api
      apiRef.current = api
    }, [])

    return e(
      'div',
      { style: { width: '100%', height: '100%' } },
      e(Excalidraw, {
        excalidrawAPI: handleApiReady,
        initialData,
        viewModeEnabled,
        onChange: (elements, appState, files) => {
          if (typeof onChange === 'function') {
            // Excalidraw fires onChange on every interaction (selection,
            // hover, scroll, …); the scene version only changes when an
            // element is genuinely added, removed, or edited. Pass it
            // through so the host can dedupe broadcasts and autosaves.
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
      if (!api) return
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
    setCollaborators(collaboratorsObject) {
      const api = apiRef.current
      if (!api) return
      const map = new Map()
      for (const [id, value] of Object.entries(collaboratorsObject || {})) {
        map.set(String(id), value)
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

import DOMPurify from 'dompurify'

/**
 * Scripts inserted through `innerHTML` never run. Replaces each script in
 * `host` with a fresh copy so the browser runs it, in document order. A
 * classic external script finishes loading before the next script runs, like
 * it would in a static page.
 *
 * Returns a promise that resolves once every script has been inserted. The
 * run stops early when `isCurrent` returns false, for instance because the
 * element re-rendered or unmounted in the meantime.
 */
export async function runInsertedScripts(host, isCurrent = () => true) {
  for (const original of Array.from(host.querySelectorAll('script'))) {
    if (!isCurrent() || !host.contains(original)) {
      return
    }

    const script = document.createElement('script')
    for (const { name, value } of Array.from(original.attributes)) {
      script.setAttribute(name, value)
    }
    script.textContent = original.textContent

    const waitForLoad =
      script.hasAttribute('src') &&
      !script.hasAttribute('async') &&
      !script.hasAttribute('defer') &&
      script.type !== 'module'
    // Dynamically inserted scripts are async unless told otherwise.
    script.async = script.hasAttribute('async')

    const loaded = waitForLoad
      ? new Promise((resolve) => {
          script.addEventListener('load', resolve, { once: true })
          script.addEventListener('error', resolve, { once: true })
        })
      : null

    original.replaceWith(script)
    if (loaded) {
      await loaded
    }
  }
}

const DEFAULT_FRAME_SANDBOX = [
  'allow-forms',
  'allow-popups',
  'allow-popups-to-escape-sandbox',
  'allow-presentation',
  'allow-scripts',
]

// Without `allow-same-origin` a framed page, even one served from the editor's
// hostname, gets an opaque origin and no access to its cookies.
function sandboxFrame(node) {
  if (node.localName !== 'iframe') {
    return
  }
  const tokens = node.hasAttribute('sandbox')
    ? node.getAttribute('sandbox').split(/\s+/).filter(Boolean)
    : DEFAULT_FRAME_SANDBOX
  node.setAttribute(
    'sandbox',
    tokens
      .filter((token) => token.toLowerCase() !== 'allow-same-origin')
      .join(' ')
  )
}

const PURIFY_CONFIG = {
  // Keeps a leading `<style>`, which would otherwise be moved to the head.
  FORCE_BODY: true,
  ADD_TAGS: ['iframe'],
  ADD_ATTR: [
    'allow',
    'allowfullscreen',
    'frameborder',
    'loading',
    'referrerpolicy',
    'sandbox',
    'target',
  ],
  // Nodes are inserted as they are, so the cleaned HTML is never parsed again.
  RETURN_DOM_FRAGMENT: true,
}

let purify = null

// Created on first use: DOMPurify needs a window, which only the client has.
function getPurify() {
  if (!purify) {
    purify = DOMPurify(window)
    purify.addHook('afterSanitizeAttributes', sandboxFrame)
  }
  return purify
}

/**
 * Parses `html` into a fragment without anything that would run JavaScript
 * once inserted: scripts, plugins, event handler attributes like `onerror`,
 * `javascript:` URLs and `srcdoc` frames. Markup, styles, forms and embeds
 * stay, and frames are sandboxed away from the page's origin. Used in Preview
 * on the editor's hostname, where code would share the editor's cookies.
 */
export function parseWithoutScripts(html) {
  return getPurify().sanitize(html, PURIFY_CONFIG)
}

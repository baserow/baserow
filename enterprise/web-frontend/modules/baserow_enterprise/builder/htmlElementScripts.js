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

// Elements that run code or load a document able to run it.
const UNSAFE_ELEMENTS = new Set([
  'script',
  'object',
  'embed',
  'applet',
  'frame',
  'frameset',
  'portal',
  'base',
  'meta',
  // SVG animations can set a link's `href` to a `javascript:` URL.
  'animate',
  'animatemotion',
  'animatetransform',
  'set',
])

const SCRIPT_URL = /^(javascript|vbscript):/i

// The URL parser skips leading control characters and spaces, and removes
// tabs and newlines anywhere, so `" java\tscript:"` still runs code.
function isScriptURL(value) {
  return SCRIPT_URL.test(
    // eslint-disable-next-line no-control-regex
    value.replace(/[\t\n\r]/g, '').replace(/^[\u0000-\u0020]+/, '')
  )
}

const DEFAULT_FRAME_SANDBOX = [
  'allow-forms',
  'allow-popups',
  'allow-popups-to-escape-sandbox',
  'allow-presentation',
  'allow-scripts',
]

function cleanElement(element) {
  for (const { name, value } of Array.from(element.attributes)) {
    if (
      name.toLowerCase().startsWith('on') ||
      name.toLowerCase() === 'srcdoc' ||
      isScriptURL(value)
    ) {
      element.removeAttribute(name)
    }
  }
  if (element.localName === 'iframe') {
    // Without `allow-same-origin` a framed page, even one served from the
    // editor's hostname, gets an opaque origin and no access to its cookies.
    const tokens = element.hasAttribute('sandbox')
      ? element.getAttribute('sandbox').split(/\s+/).filter(Boolean)
      : DEFAULT_FRAME_SANDBOX
    element.setAttribute(
      'sandbox',
      tokens
        .filter((token) => token.toLowerCase() !== 'allow-same-origin')
        .join(' ')
    )
  }
}

function cleanTree(root) {
  for (const element of Array.from(root.querySelectorAll('*'))) {
    if (UNSAFE_ELEMENTS.has(element.localName.toLowerCase())) {
      element.remove()
      continue
    }
    cleanElement(element)
    if (element.localName === 'template') {
      cleanTree(element.content)
    }
  }
}

/**
 * Parses `html` into a fragment without anything that would run JavaScript
 * once inserted: scripts, plugins, event handler attributes like `onerror`,
 * `javascript:` URLs and `srcdoc` frames. Markup, styles and embeds stay.
 * Used in Preview on the editor's hostname, where code would share the
 * editor's cookies.
 *
 * The HTML is parsed in an inert template and the cleaned nodes are inserted
 * as they are, so the browser never parses the cleaned HTML a second time.
 */
export function parseWithoutScripts(html) {
  const template = document.createElement('template')
  template.innerHTML = html
  cleanTree(template.content)
  return template.content
}

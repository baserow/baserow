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

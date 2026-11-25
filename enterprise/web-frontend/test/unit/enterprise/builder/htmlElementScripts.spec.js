import { runInsertedScripts } from '@baserow_enterprise/builder/htmlElementScripts'

// The test DOM doesn't evaluate JavaScript, so these tests check that each
// script is swapped for a fresh element, which the browser runs on insertion.
function makeHost(html) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  host.innerHTML = html
  return host
}

// The test DOM reports external scripts as loaded or failed right away. Hold
// those events back so a test decides when a script finishes loading.
function holdScriptEvents(host) {
  let holding = true
  for (const type of ['load', 'error']) {
    host.addEventListener(
      type,
      (event) => holding && event.stopImmediatePropagation(),
      true
    )
  }
  return () => {
    holding = false
  }
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('runInsertedScripts', () => {
  test('replaces scripts with fresh copies keeping attributes and code', async () => {
    const host = makeHost(
      '<p>Before</p><script type="module" data-x="1">window.a = 1</script><p>After</p>'
    )
    const original = host.querySelector('script')

    await runInsertedScripts(host)

    const script = host.querySelector('script')
    expect(script).not.toBe(original)
    expect(script.getAttribute('type')).toBe('module')
    expect(script.getAttribute('data-x')).toBe('1')
    expect(script.textContent).toBe('window.a = 1')
    expect(host.innerHTML).toBe(
      '<p>Before</p><script type="module" data-x="1">window.a = 1</script><p>After</p>'
    )
  })

  test('waits for a classic external script before running the next one', async () => {
    const host = makeHost(
      '<script src="/lib.js"></script><script>render()</script>'
    )
    const inline = host.querySelectorAll('script')[1]
    const release = holdScriptEvents(host)

    const run = runInsertedScripts(host)
    await Promise.resolve()

    const external = host.querySelector('script[src="/lib.js"]')
    expect(external.async).toBe(false)
    // The inline script is still the inert original while the library loads.
    expect(host.querySelectorAll('script')[1]).toBe(inline)

    release()
    external.dispatchEvent(new Event('load'))
    await run
    expect(host.querySelectorAll('script')[1]).not.toBe(inline)
  })

  test.each(['async', 'defer', 'type="module"'])(
    'does not wait for an external script with %s',
    async (attribute) => {
      const host = makeHost(
        `<script src="/lib.js" ${attribute}></script><script>render()</script>`
      )
      const inline = host.querySelectorAll('script')[1]

      await runInsertedScripts(host)

      expect(host.querySelectorAll('script')[1]).not.toBe(inline)
    }
  )

  test('continues after an external script fails to load', async () => {
    const host = makeHost(
      '<script src="/missing.js"></script><script>render()</script>'
    )
    const inline = host.querySelectorAll('script')[1]

    const release = holdScriptEvents(host)

    const run = runInsertedScripts(host)
    await Promise.resolve()
    expect(host.querySelectorAll('script')[1]).toBe(inline)
    release()
    host.querySelector('script').dispatchEvent(new Event('error'))
    await run

    expect(host.querySelectorAll('script')[1]).not.toBe(inline)
  })

  test('stops when the run is no longer current', async () => {
    const host = makeHost(
      '<script src="/lib.js"></script><script>render()</script>'
    )
    const inline = host.querySelectorAll('script')[1]
    let current = true
    const release = holdScriptEvents(host)

    const run = runInsertedScripts(host, () => current)
    await Promise.resolve()
    current = false
    release()
    host.querySelector('script').dispatchEvent(new Event('load'))
    await run

    expect(host.querySelectorAll('script')[1]).toBe(inline)
  })
})

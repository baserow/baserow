import autoOverflowScroll from '@baserow/modules/core/directives/autoOverflowScroll'

describe('autoOverflowScroll', () => {
  const originalResizeObserver = globalThis.ResizeObserver

  beforeEach(() => {
    globalThis.ResizeObserver = class {
      observe() {}

      disconnect() {}
    }
  })

  afterEach(() => {
    globalThis.ResizeObserver = originalResizeObserver
  })

  test('rechecks overflow when the element content is updated', () => {
    const element = document.createElement('div')
    let scrollHeight = 100
    const clientHeight = 200

    Object.defineProperties(element, {
      scrollHeight: { get: () => scrollHeight },
      clientHeight: { get: () => clientHeight },
    })

    const binding = { value: undefined, dir: autoOverflowScroll }
    autoOverflowScroll.beforeMount(element, binding)
    element.autoOverflowScrollHeightObserverFunction()

    expect(element.classList.contains('prevent-scroll')).toBe(true)

    scrollHeight = 300
    autoOverflowScroll.updated(element, binding)

    expect(element.classList.contains('prevent-scroll')).toBe(false)

    autoOverflowScroll.unmounted(element, binding)
  })
})

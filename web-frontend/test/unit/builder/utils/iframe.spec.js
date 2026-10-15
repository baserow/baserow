// @vitest-environment node
import { runInNewContext } from 'node:vm'
import { createAutoHeightEmbed } from '@baserow/modules/builder/utils/iframe'

// Browser APIs are the boundary here. Real layout (including inline line boxes,
// shrinking and third-party widgets) must also be checked in a browser.
function createEmbed({ lineGap = 0, padding = 0, margin = 0 } = {}) {
  let measuredHeight = 80
  let frame
  let onResize
  let onMutation
  const listeners = new Map()
  const posts = []
  const body = {
    querySelectorAll: () => [],
    getBoundingClientRect: () => ({
      bottom: measuredHeight + lineGap + padding,
    }),
  }
  const resizeObserver = { observe: vi.fn(), disconnect: vi.fn() }
  const mutationObserver = { observe: vi.fn(), disconnect: vi.fn() }
  const window = {
    innerHeight: 200,
    innerWidth: 400,
    scrollY: 0,
    parent: { postMessage: (message) => posts.push(message) },
    addEventListener: (name, listener) =>
      listeners.set(`window:${name}`, listener),
    removeEventListener: (name) => listeners.delete(`window:${name}`),
  }
  const document = {
    body,
    documentElement: {},
    createRange: () => ({
      selectNodeContents: () => {},
      getBoundingClientRect: () => ({ bottom: measuredHeight }),
    }),
    addEventListener: (name, listener) =>
      listeners.set(`document:${name}`, listener),
    removeEventListener: (name) => listeners.delete(`document:${name}`),
  }
  const srcdoc = createAutoHeightEmbed('')
  runInNewContext(srcdoc.slice('<script>'.length, -'</script>'.length), {
    window,
    document,
    setTimeout,
    clearTimeout,
    getComputedStyle: () => ({
      paddingBottom: String(padding),
      marginBottom: String(margin),
    }),
    requestAnimationFrame: (callback) => {
      frame = callback
      return 1
    },
    cancelAnimationFrame: () => {
      frame = null
    },
    ResizeObserver: class {
      constructor(callback) {
        onResize = callback
        return resizeObserver
      }
    },
    MutationObserver: class {
      constructor(callback) {
        onMutation = callback
        return mutationObserver
      }
    },
  })
  return {
    posts,
    window,
    listeners,
    resizeObserver,
    mutationObserver,
    resize(height) {
      measuredHeight = height
      onResize()
    },
    mutate() {
      onMutation([{ type: 'attributes' }])
    },
    flush(elapsed = 16) {
      vi.advanceTimersByTime(elapsed)
      const callback = frame
      frame = null
      callback?.(performance.now())
    },
  }
}

describe('automatic embed height script', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  test('includes inline line boxes without counting padding twice and still shrinks', () => {
    const embed = createEmbed({ lineGap: 4, padding: 10, margin: 8 })
    embed.resize(314)
    embed.flush()
    expect(embed.posts.at(-1).height).toBe(336)
    embed.window.innerHeight = 336
    embed.resize(60)
    embed.flush()
    expect(embed.posts.at(-1).height).toBe(82)
  })

  test('reports the final independent height after a rapid burst without further events', () => {
    const embed = createEmbed()
    embed.flush()
    embed.window.innerHeight = 80
    for (let height = 100; height <= 320; height += 20) {
      embed.resize(height)
      embed.flush()
      embed.window.innerHeight = embed.posts.at(-1).height
    }
    embed.flush(1000)
    expect(embed.posts.at(-1).height).toBe(320)
  })

  test('preserves original HTML and reports changing content without a viewport minimum', () => {
    const html =
      '<!doctype html><style>body{margin:0}</style><script>runWidget()</script>'
    expect(createAutoHeightEmbed(html).startsWith(html)).toBe(true)
    const embed = createEmbed()
    embed.flush()
    embed.resize(680)
    embed.resize(681)
    embed.flush()
    embed.resize(681)
    embed.flush()
    embed.resize(60)
    embed.flush()
    expect(embed.posts).toEqual([
      { type: 'baserow:embed-height', height: 80 },
      { type: 'baserow:embed-height', height: 681 },
      { type: 'baserow:embed-height', height: 60 },
    ])
  })

  test('bounds viewport feedback even when the widget mutates DOM on every resize', () => {
    const embed = createEmbed()
    for (let i = 0; i < 100; i++) {
      embed.resize(embed.window.innerHeight + 10)
      embed.mutate()
      embed.flush(1)
      embed.window.innerHeight = embed.posts.at(-1).height
    }
    // Recovery can report once more, but must not restart a slow infinite loop.
    for (let i = 0; i < 20; i++) {
      embed.flush(300)
      embed.window.innerHeight = embed.posts.at(-1).height
      embed.resize(embed.window.innerHeight + 10)
      embed.mutate()
      embed.flush()
    }
    expect(embed.posts.length).toBeLessThanOrEqual(12)
    expect(embed.window.innerHeight).toBeLessThan(400)
    // A later independent update resumes resizing.
    embed.flush(300)
    embed.resize(60)
    embed.mutate()
    embed.flush()
    expect(embed.posts.at(-1).height).toBe(60)
  })

  test('applies the final transition height after a burst of resize callbacks', () => {
    const embed = createEmbed()
    for (let height = 80; height <= 680; height += 5) {
      embed.resize(height)
      embed.flush(1)
      embed.window.innerHeight = embed.posts.at(-1).height
    }
    embed.listeners.get('document:transitionend')()
    embed.flush()
    expect(embed.posts.at(-1).height).toBe(680)
  })

  test('only answers measurement requests from its parent, including unchanged heights', () => {
    const embed = createEmbed()
    embed.flush()
    const request = embed.listeners.get('window:message')
    request({ source: {}, data: { type: 'baserow:embed-height:request' } })
    embed.flush()
    expect(embed.posts).toHaveLength(1)
    request({
      source: embed.window.parent,
      data: { type: 'baserow:embed-height:request' },
    })
    embed.flush()
    expect(embed.posts).toHaveLength(2)
    expect(embed.posts[1].height).toBe(80)
  })

  test('disconnects observers and cancels queued measurements on navigation', () => {
    const embed = createEmbed()
    embed.listeners.get('window:pagehide')()
    embed.flush()
    expect(embed.posts).toHaveLength(0)
    expect(embed.resizeObserver.disconnect).toHaveBeenCalled()
    expect(embed.mutationObserver.disconnect).toHaveBeenCalled()
    expect(embed.listeners.has('window:message')).toBe(false)
    expect(embed.listeners.has('window:resize')).toBe(false)
    expect(embed.listeners.has('document:load')).toBe(false)
  })

  test('cancels a pending recovery report on navigation', () => {
    const embed = createEmbed()
    for (let i = 0; i < 12; i++) {
      embed.resize(embed.window.innerHeight + 10)
      embed.flush()
      embed.window.innerHeight = embed.posts.at(-1).height
    }
    expect(vi.getTimerCount()).toBe(1)
    const count = embed.posts.length
    embed.listeners.get('window:pagehide')()
    embed.flush(1000)
    expect(embed.posts).toHaveLength(count)
    expect(vi.getTimerCount()).toBe(0)
  })
})

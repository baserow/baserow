import { mountSuspended } from '@nuxt/test-utils/runtime'
import { nextTick } from 'vue'
import IFrameElement from '@baserow/modules/builder/components/elements/components/IFrameElement.vue'

describe('IFrameElement', () => {
  const wrappers = []
  beforeEach(() => {
    // Detached happy-dom iframes have no browsing context. Give each iframe
    // a distinct window identity without executing third-party srcdoc scripts.
    const windows = new WeakMap()
    vi.spyOn(
      HTMLIFrameElement.prototype,
      'contentWindow',
      'get'
    ).mockImplementation(function () {
      if (!windows.has(this)) windows.set(this, { postMessage: vi.fn() })
      return windows.get(this)
    })
  })
  afterEach(() => {
    wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    vi.restoreAllMocks()
  })
  const mountComponent = (
    mode,
    elementValues = {},
    applicationContextMode = mode
  ) => {
    const page = {}
    const builder = { id: 1, theme: {} }
    const element = {
      id: 1,
      type: 'iframe',
      source_type: 'embed',
      embed: {
        formula: '"<script>window.parent.document.cookie</script>"',
      },
      height: 300,
      styles: {},
      ...elementValues,
    }

    return mountSuspended(IFrameElement, {
      props: { element },
      global: {
        provide: {
          workspace: {},
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext: { builder, page, mode: applicationContextMode },
        },
      },
    }).then((wrapper) => {
      wrappers.push(wrapper)
      return wrapper
    })
  }

  test.each(['editing', 'preview', 'public'])(
    'automatically grows and shrinks embedded content in %s mode',
    async (mode) => {
      const wrapper = await mountComponent(mode, { auto_height: true })
      const iframe = wrapper.find('iframe')
      expect(iframe.attributes('height')).toBe('300')
      for (const height of [680, 120]) {
        window.dispatchEvent(
          new MessageEvent('message', {
            source: iframe.element.contentWindow,
            origin: 'null',
            data: { type: 'baserow:embed-height', height },
          })
        )
        await nextTick()
        expect(iframe.attributes('height')).toBe(String(height))
      }
      expect(iframe.attributes('sandbox')).toBe(
        mode === 'editing' ? 'allow-scripts' : undefined
      )
    }
  )

  test('allows embedded scripts in an isolated editing sandbox', async () => {
    const wrapper = await mountComponent('editing')

    expect(wrapper.find('iframe').element).toMatchSnapshot()
  })

  test.each([
    null,
    {},
    'not a message',
    { type: 'other', height: 500 },
    ...[-1, 1.5, NaN, Infinity, '500', null, Number.MAX_SAFE_INTEGER + 1].map(
      (height) => ({ type: 'baserow:embed-height', height })
    ),
  ])('ignores an invalid height message %j', async (data) => {
    const wrapper = await mountComponent('preview', { auto_height: true })
    const iframe = wrapper.find('iframe')
    window.dispatchEvent(
      new MessageEvent('message', {
        source: iframe.element.contentWindow,
        data,
      })
    )
    await nextTick()
    expect(iframe.attributes('height')).toBe('300')
  })

  test('ignores another iframe even when its origin is opaque', async () => {
    const wrapper = await mountComponent('editing', { auto_height: true })
    const other = await mountComponent('editing', { auto_height: true })
    window.dispatchEvent(
      new MessageEvent('message', {
        source: other.find('iframe').element.contentWindow,
        origin: 'null',
        data: { type: 'baserow:embed-height', height: 680 },
      })
    )
    await nextTick()
    expect(wrapper.find('iframe').attributes('height')).toBe('300')
    expect(other.find('iframe').attributes('height')).toBe('680')
  })

  test.each([
    { auto_height: false },
    {
      source_type: 'url',
      url: { formula: '"https://example.com"' },
      auto_height: true,
    },
  ])(
    'keeps fixed height when automatic resizing is inactive %j',
    async (values) => {
      const wrapper = await mountComponent('preview', values)
      const iframe = wrapper.find('iframe')
      window.dispatchEvent(
        new MessageEvent('message', {
          source: iframe.element.contentWindow,
          data: { type: 'baserow:embed-height', height: 680 },
        })
      )
      await nextTick()
      expect(iframe.attributes('height')).toBe('300')
      expect(iframe.attributes('srcdoc') || '').not.toContain(
        'baserow:embed-height'
      )
    }
  )

  test('resets height on content replacement and rejects messages from the old document', async () => {
    const wrapper = await mountComponent('preview', { auto_height: true })
    const oldSource = wrapper.find('iframe').element.contentWindow
    const send = async (source, height) => {
      window.dispatchEvent(
        new MessageEvent('message', {
          source,
          data: { type: 'baserow:embed-height', height },
        })
      )
      await nextTick()
    }
    await send(oldSource, 680)
    await wrapper.setProps({
      element: {
        ...wrapper.props('element'),
        embed: { formula: '"<div>New content</div>"' },
      },
    })
    expect(wrapper.find('iframe').attributes('height')).toBe('300')
    await send(oldSource, 900)
    expect(wrapper.find('iframe').attributes('height')).toBe('300')
    await send(wrapper.find('iframe').element.contentWindow, 80)
    expect(wrapper.find('iframe').attributes('height')).toBe('80')
    await wrapper.find('iframe').trigger('load')
    expect(wrapper.find('iframe').attributes('height')).toBe('300')
    await send(wrapper.find('iframe').element.contentWindow, 80)
    expect(wrapper.find('iframe').attributes('height')).toBe('80')
    await wrapper.setProps({
      element: { ...wrapper.props('element'), auto_height: false },
    })
    expect(wrapper.find('iframe').attributes('height')).toBe('300')
    expect(wrapper.find('iframe').attributes('srcdoc')).toBe(
      '<div>New content</div>'
    )
  })

  test('removes its message listener when unmounted', async () => {
    const add = vi.spyOn(window, 'addEventListener')
    const remove = vi.spyOn(window, 'removeEventListener')
    const wrapper = await mountComponent('preview', { auto_height: true })
    const listener = add.mock.calls.find(([name]) => name === 'message')[1]
    wrapper.unmount()
    expect(remove).toHaveBeenCalledWith('message', listener)
    add.mockRestore()
    remove.mockRestore()
  })

  test('shows an editor placeholder for resolved external URLs', async () => {
    const wrapper = await mountComponent('editing', {
      source_type: 'url',
      url: { formula: '"https://example.com"' },
    })

    const placeholder = wrapper.find('.iframe-element__editor-placeholder')

    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(placeholder.attributes('style')).toBe('height: 300px;')
    expect(placeholder.text()).toBe(
      'iframeElementForm.editorPreviewPlaceholder'
    )
  })

  test('keeps the existing empty state for unresolved external URLs', async () => {
    const wrapper = await mountComponent('editing', {
      source_type: 'url',
      url: { formula: '""' },
    })

    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.find('.iframe-element__editor-placeholder').exists()).toBe(
      false
    )
    expect(wrapper.find('.iframe-element__empty').text()).toBe(
      'iframeElementForm.emptyValue'
    )
  })

  test('does not sandbox user-provided content in preview mode', async () => {
    const wrapper = await mountComponent('preview')

    expect(wrapper.find('iframe').element).toMatchSnapshot()
  })

  test('allows restricted capabilities for external URLs in preview mode', async () => {
    const wrapper = await mountComponent('preview', {
      source_type: 'url',
      url: { formula: '"https://example.com"' },
    })

    expect(wrapper.find('iframe').element).toMatchSnapshot()
  })

  test.each(['preview', 'public'])(
    'allows a trusted external URL to use its own origin in %s mode',
    async (mode) => {
      const wrapper = await mountComponent(mode, {
        source_type: 'url',
        url: { formula: '"https://example.com"' },
        allow_same_origin: true,
      })

      expect(wrapper.find('iframe').attributes('sandbox')).toBe(
        'allow-scripts allow-forms allow-popups allow-same-origin'
      )
    }
  )

  test('shows an editor placeholder for trusted URLs in editing mode', async () => {
    const wrapper = await mountComponent('editing', {
      source_type: 'url',
      url: { formula: '"https://example.com"' },
      allow_same_origin: true,
    })

    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.find('.iframe-element__editor-placeholder').exists()).toBe(
      true
    )
  })

  test('shows an editor placeholder when the editor force-renders URLs in public mode', async () => {
    const wrapper = await mountComponent(
      'public',
      {
        source_type: 'url',
        url: { formula: '"https://example.com"' },
        allow_same_origin: true,
      },
      'editing'
    )

    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.find('.iframe-element__editor-placeholder').exists()).toBe(
      true
    )
  })

  test.each([
    ['same-origin', window.location.origin],
    ['relative', '/embedded-resource'],
    ['invalid', 'not a valid URL'],
  ])('keeps a trusted %s URL sandboxed', async (_description, url) => {
    const wrapper = await mountComponent('preview', {
      source_type: 'url',
      url: { formula: JSON.stringify(url) },
      allow_same_origin: true,
    })

    expect(wrapper.find('iframe').attributes('sandbox')).toBe(
      'allow-scripts allow-forms allow-popups'
    )
  })

  test('does not change sandboxing for trusted embedded content', async () => {
    const wrapper = await mountComponent('preview', {
      allow_same_origin: true,
    })

    expect(wrapper.find('iframe').attributes('sandbox')).toBeUndefined()
  })

  test('allows restricted capabilities for external URLs in public mode', async () => {
    const wrapper = await mountComponent('public', {
      source_type: 'url',
      url: { formula: '"https://example.com"' },
    })

    expect(wrapper.find('iframe').element).toMatchSnapshot()
  })
})

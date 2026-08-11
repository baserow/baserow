import { mountSuspended } from '@nuxt/test-utils/runtime'
import IFrameElement from '@baserow/modules/builder/components/elements/components/IFrameElement.vue'

describe('IFrameElement', () => {
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
    })
  }

  test('allows embedded scripts in an isolated editing sandbox', async () => {
    const wrapper = await mountComponent('editing')

    expect(wrapper.find('iframe').element).toMatchSnapshot()
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

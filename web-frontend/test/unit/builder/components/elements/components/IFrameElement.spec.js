import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount } from '@vue/test-utils'
import IFrameElement from '@baserow/modules/builder/components/elements/components/IFrameElement.vue'

enableAutoUnmount(afterEach)

describe('IFrameElement', () => {
  const mountComponent = (
    mode,
    elementValues = {},
    applicationContextMode = mode,
    untrustedContent = false
  ) => {
    const page = {}
    const builder = { id: 1, theme: {}, untrusted_content: untrustedContent }
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

  test.each([
    ['editing', 'editing'],
    ['public', 'editing'],
  ])(
    'shows an informational hint alongside HTML in %s mode within the %s context',
    async (mode, applicationContextMode) => {
      const html = '<p>Visible embedded content</p>'
      const wrapper = await mountComponent(
        mode,
        { embed: { formula: JSON.stringify(html) } },
        applicationContextMode
      )

      expect(wrapper.find('iframe').attributes('srcdoc')).toBe(html)
      expect(wrapper.find('iframe').attributes('height')).toBe('300')
      const hint = wrapper.get('.iframe-element__editor-hint')
      expect(hint.attributes('aria-label')).toBe(
        'iframeElementForm.editorEmbedHint'
      )

      await hint.trigger('mouseenter')
      expect(document.querySelector('.tooltip').textContent).toBe(
        'iframeElementForm.editorEmbedHint'
      )
      await hint.trigger('keydown', { key: 'Escape' })
      expect(document.querySelector('.tooltip')).toBeNull()
    }
  )

  test('makes the embed hint available on keyboard focus and dismissible', async () => {
    const wrapper = await mountComponent('editing')
    const hint = wrapper.get('button.iframe-element__editor-hint')

    await hint.trigger('focus')
    expect(document.querySelector('.tooltip').textContent).toBe(
      'iframeElementForm.editorEmbedHint'
    )

    await hint.trigger('keydown', { key: 'Escape' })
    expect(document.querySelector('.tooltip')).toBeNull()

    await hint.trigger('focus')
    await hint.trigger('blur')
    expect(document.querySelector('.tooltip')).toBeNull()
  })

  test.each(['preview', 'public'])(
    'omits the embed hint in %s mode',
    async (mode) => {
      const wrapper = await mountComponent(mode)

      expect(wrapper.find('iframe').exists()).toBe(true)
      expect(wrapper.find('.iframe-element__editor-hint').exists()).toBe(false)
    }
  )

  test.each([null, { formula: '""' }])(
    'keeps the empty HTML state without an embed hint for %j',
    async (embed) => {
      const wrapper = await mountComponent('editing', { embed })

      expect(wrapper.find('.iframe-element__empty').exists()).toBe(true)
      expect(wrapper.find('iframe').exists()).toBe(false)
      expect(wrapper.find('.iframe-element__editor-hint').exists()).toBe(false)
    }
  )

  test('shows an editor placeholder for resolved external URLs', async () => {
    const wrapper = await mountComponent('editing', {
      source_type: 'url',
      url: { formula: '"https://example.com"' },
    })

    const placeholder = wrapper.find('.iframe-element__editor-placeholder')

    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.find('.iframe-element__editor-hint').exists()).toBe(false)
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
  test.each(['editing', 'preview', 'public'])(
    'blocks embedded HTML and URL iframes in %s mode',
    async (mode) => {
      for (const source_type of ['embed', 'url']) {
        const wrapper = await mountComponent(
          mode,
          {
            source_type,
            url: { formula: '"https://example.com"' },
            allow_same_origin: true,
          },
          mode,
          true
        )
        expect(wrapper.html()).toMatchSnapshot()
        expect(wrapper.find('iframe').exists()).toBe(false)
        expect(wrapper.find('.iframe-element__editor-hint').exists()).toBe(
          false
        )
      }
    }
  )
})

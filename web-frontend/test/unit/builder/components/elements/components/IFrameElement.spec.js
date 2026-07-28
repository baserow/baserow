import { mountSuspended } from '@nuxt/test-utils/runtime'
import IFrameElement from '@baserow/modules/builder/components/elements/components/IFrameElement.vue'

describe('IFrameElement', () => {
  const mountComponent = (mode, elementValues = {}) => {
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
          applicationContext: { builder, page, mode },
        },
      },
    })
  }

  test('allows embedded scripts in an isolated editing sandbox', async () => {
    const wrapper = await mountComponent('editing')

    expect(wrapper.find('iframe').element).toMatchSnapshot()
  })

  test('fully sandboxes external URLs in editing mode', async () => {
    const wrapper = await mountComponent('editing', {
      source_type: 'url',
      url: { formula: '"https://example.com"' },
    })

    expect(wrapper.find('iframe').element).toMatchSnapshot()
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

  test('allows restricted capabilities for external URLs in public mode', async () => {
    const wrapper = await mountComponent('public', {
      source_type: 'url',
      url: { formula: '"https://example.com"' },
    })

    expect(wrapper.find('iframe').element).toMatchSnapshot()
  })
})

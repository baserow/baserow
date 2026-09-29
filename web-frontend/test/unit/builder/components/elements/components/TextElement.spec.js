import { mountSuspended } from '@nuxt/test-utils/runtime'
import TextElement from '@baserow/modules/builder/components/elements/components/TextElement.vue'

describe('TextElement', () => {
  test('renders Markdown with the Application Builder rules', async () => {
    const page = {}
    const builder = { id: 1, theme: {} }
    const mode = 'public'
    const element = {
      id: 1,
      type: 'text',
      value: { mode: 'raw', formula: '# Heading\n\n`inline code`' },
      format: 'markdown',
      styles: {},
    }

    const wrapper = await mountSuspended(TextElement, {
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

    expect(wrapper.find('.ab-heading').text()).toBe('Heading')
    expect(wrapper.find('.ab-code--inline').text()).toBe('inline code')
  })
})
